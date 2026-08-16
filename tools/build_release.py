#!/usr/bin/env python3
"""Build a deterministic BBK zip release and companion artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Sequence

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runtime_requirements import enforce_supported_python, normalize_python_command, python_command, python_environment

enforce_supported_python(program='BBK release builder')

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
TOP = f"bbk-{VERSION}"
FIXED_TIME = (2026, 8, 7, 0, 0, 0)
PACKAGE_CREATED_AT = "2026-08-07T00:00:00Z"
PROFILE_GENERATED_AT = "2026-08-07T00:00:00-06:00"
# Governance, execution, and interpreter state are never release subjects.
# Keep this identical to the package verifier so a direct source-root build
# and its strict readback select the same files.
EXCLUDED_PARTS = {".git", ".bbk", "evidence", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
INCLUDED_EVIDENCE_FILES = frozenset({
    "evidence/alpha17-rc6-work-unit-dispositions.json",
    "evidence/qualification/deepseek-codex-provider-seam-r4/qualification-receipt.json",
    "evidence/qualification/omp-host-contract-rc9.json",
    "evidence/qualification/session-inspector-oracle-alpha17.json",
})
# Candidate metadata is a carrier/control descriptor for the qualification
# attempt, not a governed product subject in a strict source mirror.
EXCLUDED_ROOT_FILES = frozenset({"candidate.json"})
# The root manifest is a package control carrier.  It is included in the
# materialized release/mirror closure, but intentionally excluded from its own
# generated ``files`` list so the root digest remains non-self-referential.
MANDATORY_CONTROL_FILES = ("PACKAGE-MANIFEST.json",)
# Package executability is an explicit release contract, not an accident of the
# build host checkout. Alpha.13 exposes every command through an interpreter, so
# the source archive intentionally has no native executable entrypoints.
PACKAGE_EXECUTABLES: frozenset[str] = frozenset()


def run(command: Sequence[str]) -> None:
    values = normalize_python_command(command)
    subprocess.run(values, cwd=ROOT, env=python_environment(), check=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def package_files() -> Iterable[Path]:
    for path in sorted(ROOT.rglob("*"), key=lambda item: item.relative_to(ROOT).as_posix()):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if (any(part in EXCLUDED_PARTS for part in rel.parts) and rel.as_posix() not in INCLUDED_EVIDENCE_FILES) or path.suffix in EXCLUDED_SUFFIXES:
            continue
        if rel.as_posix() == "PACKAGE-MANIFEST.json" or rel.as_posix() in EXCLUDED_ROOT_FILES:
            continue
        yield path


def is_executable(path: Path) -> bool:
    return path.relative_to(ROOT).as_posix() in PACKAGE_EXECUTABLES


def build_manifest() -> dict[str, Any]:
    files = []
    for path in package_files():
        rel = path.relative_to(ROOT).as_posix()
        files.append({"path": rel, "bytes": path.stat().st_size, "sha256": sha256_file(path), "executable": is_executable(path)})
    payload = {"schema": "bbk.package-root.v1", "name": "Blueprint Bootstrap Kit", "version": VERSION, "files": files}
    projection = json.loads((ROOT / "projections" / "manifest.json").read_text(encoding="utf-8"))
    return {
        "schema": "bbk.package-manifest.v1", "name": "Blueprint Bootstrap Kit", "version": VERSION,
        "created_at": PACKAGE_CREATED_AT, "file_count": len(files), "files": files,
        "root_sha256": hashlib.sha256(canonical(payload)).hexdigest(),
        "targets": projection.get("targets", []), "role_count": projection.get("role_count"),
        "projection_count": projection.get("projection_count"), "projection_source_sha256": projection.get("source_sha256"),
        "model_routing_schema": projection.get("model_routing_schema"),
        "model_routing_mode": projection.get("model_routing_mode"),
        "model_route_count": projection.get("model_route_count"),
        "model_routing_source_sha256": projection.get("model_routing_source_sha256"),
        "authority_disclaimer": "BBK is a temporary method harness and is not an official Blueprint release or authority-bearing package.",
    }


def refresh_bundled_profile_integrity() -> dict[str, Any]:
    """Rebuild the public profile inventory from the archives that are present."""
    bundle_root = ROOT / "bundled-language-profiles"
    packages_root = bundle_root / "packages"
    archives = sorted(packages_root.glob("*.zip"), key=lambda item: item.name.casefold())
    if not archives:
        raise RuntimeError(f"No bundled language-profile archives found in {packages_root}")

    expected_companions: set[Path] = set()
    profile_versions: dict[str, str] = {}
    sum_lines: list[str] = []
    for archive in archives:
        digest = sha256_file(archive)
        companion = archive.with_name(archive.name + ".sha256")
        companion.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
        expected_companions.add(companion.resolve())
        sum_lines.append(f"{digest}  packages/{archive.name}\n")

        with zipfile.ZipFile(archive) as source:
            candidates = [
                name
                for name in source.namelist()
                if len(PurePosixPath(name).parts) == 2
                and PurePosixPath(name).name == "PROFILE.json"
            ]
            if len(candidates) != 1:
                raise RuntimeError(
                    f"Expected one top-level PROFILE.json in {archive}, found {len(candidates)}"
                )
            profile = json.loads(source.read(candidates[0]).decode("utf-8"))
        profile_id = profile.get("id")
        version = profile.get("version")
        if not isinstance(profile_id, str) or not profile_id:
            raise RuntimeError(f"Invalid profile id in {archive}")
        if not isinstance(version, str) or not version:
            raise RuntimeError(f"Invalid profile version in {archive}")
        if profile_id in profile_versions:
            raise RuntimeError(f"Duplicate bundled profile id: {profile_id}")
        profile_versions[profile_id] = version

    for companion in packages_root.glob("*.zip.sha256"):
        if companion.resolve() not in expected_companions:
            companion.unlink()

    (bundle_root / "SHA256SUMS.txt").write_text("".join(sum_lines), encoding="utf-8")
    manifest_path = bundle_root / "RELEASE-MANIFEST.json"
    previous: dict[str, Any] = {}
    if manifest_path.is_file():
        try:
            value = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                previous = value
        except json.JSONDecodeError:
            previous = {}

    files = []
    for path in sorted(bundle_root.rglob("*"), key=lambda item: item.relative_to(bundle_root).as_posix()):
        if not path.is_file() or path == manifest_path:
            continue
        files.append({
            "path": path.relative_to(bundle_root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    manifest = {
        "schema": "bbk.language-profiles-release-bundle-manifest.v1",
        "release": f"bbk-{VERSION}-language-profiles",
        "variant": f"bundled-with-bbk-{VERSION}",
        "status": "PASS",
        "generatedAt": PROFILE_GENERATED_AT,
        "timezone": previous.get("timezone", "America/Edmonton"),
        "fileCount": len(files),
        "profileVersions": dict(sorted(profile_versions.items())),
        "files": files,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def write_manifest() -> dict[str, Any]:
    manifest = build_manifest()
    (ROOT / "PACKAGE-MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def zip_info(name: str, executable: bool) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, FIXED_TIME)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_DEFLATED
    mode = (stat.S_IFREG | (0o755 if executable else 0o644)) << 16
    info.external_attr = mode
    return info


def build_zip(output: Path, manifest: dict[str, Any]) -> None:
    all_files = package_control_closure(manifest)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(all_files, key=lambda p: p.relative_to(ROOT).as_posix()):
            rel = path.relative_to(ROOT).as_posix()
            executable = is_executable(path)
            archive.writestr(zip_info(f"{TOP}/{rel}", executable), path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def package_control_closure(manifest: dict[str, Any], root: Path = ROOT) -> list[Path]:
    """Return package files plus mandatory controls for a mirror/archive.

    Controls are a separate closure: ``PACKAGE-MANIFEST.json`` must travel
    with a materialized package but cannot list itself in the generated
    manifest.  Keeping this selection in the canonical builder makes the
    distinction explicit and testable.
    """
    return [root / item["path"] for item in manifest["files"]] + [root / name for name in MANDATORY_CONTROL_FILES]


def qualification_checks() -> None:
    """Run the same ordered verification surface exposed to package users."""
    run(python_command(
        ROOT / "tools" / "run_tests.py", "--all", "--profile", "release",
        "--require-node", "--mode", "pooled", "--jobs", "0",
    ))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(ROOT.parent))
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--manifest-only", action="store_true")
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    # Refresh the nested profile bundle first so deleted or added optional
    # profiles cannot leave stale checksums or inventory records behind.
    refresh_bundled_profile_integrity()
    # PACKAGE-MANIFEST.json is excluded from its own root digest, so write it
    # before qualification and use it as the pre-execution trust gate.
    manifest = write_manifest()
    if args.manifest_only:
        print(f"Package root SHA-256: {manifest['root_sha256']}")
        print(f"Files: {manifest['file_count']}")
        return 0
    if not args.skip_tests:
        qualification_checks()
    manifest = write_manifest()
    run(python_command(ROOT / "tools" / "verify_package.py", "--strict-mode"))
    archive = output_dir / f"{TOP}.zip"
    build_zip(archive, manifest)
    digest = sha256_file(archive)
    sha_path = output_dir / f"{TOP}.sha256"
    sha_path.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    manifest_path = output_dir / f"{TOP}-package-manifest.json"
    shutil.copy2(ROOT / "PACKAGE-MANIFEST.json", manifest_path)
    notes_path = output_dir / f"{TOP}-release-notes.md"
    shutil.copy2(ROOT / "RELEASE-NOTES.md", notes_path)
    print(f"Built: {archive}")
    print(f"SHA-256: {digest}")
    print(f"Package root SHA-256: {manifest['root_sha256']}")
    print(f"Files: {manifest['file_count']}")
    print(f"Targets: {', '.join(manifest['targets'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
