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
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
TOP = f"bbk-{VERSION}"
FIXED_TIME = (2026, 8, 3, 0, 0, 0)
EXCLUDED_PARTS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
# Package executability is an explicit release contract, not an accident of the
# build host checkout. Alpha.13 exposes every command through an interpreter, so
# the source archive intentionally has no native executable entrypoints.
PACKAGE_EXECUTABLES: frozenset[str] = frozenset()


def run(command: Sequence[str]) -> None:
    subprocess.run([str(x) for x in command], cwd=ROOT, check=True)


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
        if any(part in EXCLUDED_PARTS for part in rel.parts) or path.suffix in EXCLUDED_SUFFIXES:
            continue
        if rel.as_posix() == "PACKAGE-MANIFEST.json":
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
        "created_at": "2026-08-03T00:00:00Z", "file_count": len(files), "files": files,
        "root_sha256": hashlib.sha256(canonical(payload)).hexdigest(),
        "targets": projection.get("targets", []), "role_count": projection.get("role_count"),
        "projection_count": projection.get("projection_count"), "projection_source_sha256": projection.get("source_sha256"),
        "model_routing_schema": projection.get("model_routing_schema"),
        "model_routing_mode": projection.get("model_routing_mode"),
        "model_route_count": projection.get("model_route_count"),
        "model_routing_source_sha256": projection.get("model_routing_source_sha256"),
        "authority_disclaimer": "BBK is a temporary method harness and is not an official Blueprint release or authority-bearing package.",
    }


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
    all_files = [ROOT / item["path"] for item in manifest["files"]] + [ROOT / "PACKAGE-MANIFEST.json"]
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(all_files, key=lambda p: p.relative_to(ROOT).as_posix()):
            rel = path.relative_to(ROOT).as_posix()
            executable = is_executable(path)
            archive.writestr(zip_info(f"{TOP}/{rel}", executable), path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def qualification_checks() -> None:
    """Run the same ordered verification surface exposed to package users."""
    run([
        sys.executable, "tools/run_tests.py", "--all", "--profile", "release",
        "--require-node", "--mode", "pooled", "--jobs", "0",
    ])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(ROOT.parent))
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    # PACKAGE-MANIFEST.json is excluded from its own root digest, so write it
    # before qualification and use it as the pre-execution trust gate.
    manifest = write_manifest()
    if not args.skip_tests:
        qualification_checks()
    manifest = write_manifest()
    run([sys.executable, "tools/verify_package.py", "--strict-mode"])
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
