#!/usr/bin/env python3
"""Prepare verified BBK language-profile packages for the core installer.

Accepted sources are an extracted profile root, an individual profile ZIP, a
flat or ``packages/``-based directory of extracted profiles, an extracted
profile-source repository, an extracted multi-profile release bundle, or a ZIP
containing one of those layouts. Extraction is traversal-safe and every
profile package manifest is verified before the core installer writes any
destination.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Sequence

from bbk import profile_compatibility, verify_profile_package
from contracts import validate_profile

MAX_ZIP_ENTRIES = 20_000
MAX_ZIP_UNCOMPRESSED_BYTES = 1_500_000_000
PROFILE_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
WINDOWS_RESERVED_NAMES = {
    "con", "prn", "aux", "nul",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


class ProfileInstallError(RuntimeError):
    """A profile source is unsafe, malformed, incompatible, or unverifiable."""


ProgressCallback = Callable[[str], None]


def _progress(callback: ProgressCallback | None, message: str) -> None:
    if callback is not None:
        callback(message)


@dataclass(frozen=True)
class PreparedProfile:
    """One verified profile package rooted in temporary or caller-owned storage."""

    root: Path
    profile: dict[str, Any]
    source: str
    source_sha256: str | None
    package_verification: dict[str, Any]
    compatibility: dict[str, Any]
    bundle_source: str | None = None

    @property
    def profile_id(self) -> str:
        return str(self.profile["id"])

    @property
    def version(self) -> str:
        return str(self.profile["version"])

    @property
    def package_name(self) -> str:
        return str(self.profile.get("package") or f"bbk-profile-{self.profile_id}")

    @property
    def root_sha256(self) -> str:
        return str(self.package_verification.get("root_sha256") or "")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value: str, *, label: str) -> PurePosixPath:
    if not value or "\\" in value or "\x00" in value or any(ord(char) < 32 for char in value):
        raise ProfileInstallError(f"unsafe {label}: {value!r}")
    # Validate raw segments before PurePosixPath can normalize ``.`` or repeated
    # separators away.  The same portable subset is used on every host.
    segments = value.split("/")
    if value.startswith("/") or any(segment in {"", ".", ".."} for segment in segments):
        raise ProfileInstallError(f"unsafe {label}: {value!r}")
    for segment in segments:
        if ":" in segment or segment.endswith((" ", ".")):
            raise ProfileInstallError(f"Windows-unsafe {label}: {value!r}")
        stem = segment.split(".", 1)[0].casefold()
        if stem in WINDOWS_RESERVED_NAMES:
            raise ProfileInstallError(f"reserved-device {label}: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise ProfileInstallError(f"unsafe {label}: {value!r}")
    return path


def _zip_mode(info: zipfile.ZipInfo) -> int:
    return (info.external_attr >> 16) & 0xFFFF


def _zip_is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_IFMT(_zip_mode(info)) == stat.S_IFLNK


def _zip_is_special(info: zipfile.ZipInfo) -> bool:
    kind = stat.S_IFMT(_zip_mode(info))
    return kind not in {0, stat.S_IFREG, stat.S_IFDIR}


def safe_extract_zip(archive_path: Path, destination: Path) -> None:
    """Extract *archive_path* after complete portable-path validation."""
    try:
        archive = zipfile.ZipFile(archive_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ProfileInstallError(f"invalid ZIP {archive_path}: {exc}") from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            raise ProfileInstallError(f"ZIP has too many entries ({len(infos)}): {archive_path}")
        total = sum(max(info.file_size, 0) for info in infos)
        if total > MAX_ZIP_UNCOMPRESSED_BYTES:
            raise ProfileInstallError(f"ZIP expands beyond the safety limit: {archive_path}")

        validated: list[tuple[zipfile.ZipInfo, PurePosixPath, str]] = []
        seen_exact: set[str] = set()
        seen_folded_prefixes: dict[str, str] = {}
        file_keys: set[str] = set()
        directory_keys: set[str] = set()
        for info in infos:
            if info.flag_bits & 0x1:
                raise ProfileInstallError(f"encrypted ZIP entry is unsupported: {info.filename}")
            raw = info.filename.rstrip("/")
            rel = _safe_relative(raw, label="ZIP entry") if raw else None
            if rel is None:
                continue
            key = rel.as_posix()
            if key in seen_exact:
                raise ProfileInstallError(f"duplicate ZIP entry: {key}")
            seen_exact.add(key)
            if _zip_is_symlink(info):
                raise ProfileInstallError(f"ZIP symlink is not allowed: {key}")
            if _zip_is_special(info):
                raise ProfileInstallError(f"ZIP special-file entry is not allowed: {key}")

            for index in range(1, len(rel.parts) + 1):
                prefix = PurePosixPath(*rel.parts[:index]).as_posix()
                folded = prefix.casefold()
                previous = seen_folded_prefixes.get(folded)
                if previous is not None and previous != prefix:
                    raise ProfileInstallError(
                        f"portable-path collision in ZIP: {previous!r} and {prefix!r}"
                    )
                seen_folded_prefixes[folded] = prefix
            folded_key = key.casefold()
            (directory_keys if info.is_dir() else file_keys).add(folded_key)
            validated.append((info, rel, key))

        for file_key in sorted(file_keys):
            if file_key in directory_keys:
                raise ProfileInstallError(
                    f"ZIP file/directory path conflict: {seen_folded_prefixes[file_key]}"
                )
            prefix = file_key + "/"
            descendants = [value for value in seen_folded_prefixes if value.startswith(prefix)]
            if descendants:
                raise ProfileInstallError(
                    f"ZIP file/directory path conflict: {seen_folded_prefixes[file_key]}"
                )

        extracted_bytes = 0
        for info, rel, _key in validated:
            target = destination.joinpath(*rel.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, target.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    extracted_bytes += len(chunk)
                    if extracted_bytes > MAX_ZIP_UNCOMPRESSED_BYTES:
                        raise ProfileInstallError(f"ZIP expands beyond the safety limit: {archive_path}")
                    output.write(chunk)
            mode = _zip_mode(info) & 0o777
            if mode:
                os.chmod(target, mode)


def _profile_roots(root: Path) -> list[Path]:
    """Return supported extracted profile roots without unbounded recursion.

    A profile source may be one package, a flat repository whose immediate
    children are packages, or a conventional repository with packages beneath
    ``packages/``. Restricting discovery to these explicit levels keeps source
    selection deterministic and prevents unrelated nested fixtures from being
    mistaken for installable profiles.
    """
    values: list[Path] = []
    bases = [root]
    packages = root / "packages"
    if packages.is_dir():
        bases.append(packages)
    for base in bases:
        if (base / "PROFILE.json").is_file() and (base / "PACKAGE-MANIFEST.json").is_file():
            values.append(base)
        for profile in base.glob("*/PROFILE.json"):
            if (profile.parent / "PACKAGE-MANIFEST.json").is_file():
                values.append(profile.parent)
    return sorted({path.resolve() for path in values})


def _repository_roots(root: Path) -> list[Path]:
    values: list[Path] = []
    if (root / "REPOSITORY-MANIFEST.json").is_file() and (root / "packages").is_dir():
        values.append(root)
    for manifest in root.glob("*/REPOSITORY-MANIFEST.json"):
        if (manifest.parent / "packages").is_dir():
            values.append(manifest.parent)
    return sorted({path.resolve() for path in values})


def _bundle_roots(root: Path) -> list[Path]:
    values: list[Path] = []
    if (root / "RELEASE-MANIFEST.json").is_file() and (root / "packages").is_dir():
        values.append(root)
    for manifest in root.glob("*/RELEASE-MANIFEST.json"):
        if (manifest.parent / "packages").is_dir():
            values.append(manifest.parent)
    return sorted({path.resolve() for path in values})


def verify_bundle_manifest(bundle_root: Path) -> dict[str, Any]:
    path = bundle_root / "RELEASE-MANIFEST.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileInstallError(f"invalid release manifest {path}: {exc}") from exc
    if value.get("schema") != "bbk.language-profiles-release-bundle-manifest.v1":
        raise ProfileInstallError(
            f"unsupported release-manifest schema {value.get('schema')!r}: {path}"
        )
    if value.get("status") != "PASS":
        raise ProfileInstallError(
            f"release bundle is not qualified PASS (status={value.get('status')!r}): {path}"
        )
    records = value.get("files")
    if not isinstance(records, list):
        raise ProfileInstallError(f"release manifest files must be a list: {path}")
    expected: dict[str, dict[str, Any]] = {}
    portable_expected: dict[str, str] = {}
    for item in records:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ProfileInstallError(f"invalid release-manifest file record: {item!r}")
        rel = _safe_relative(item["path"], label="release-manifest path").as_posix()
        portable_key = rel.casefold()
        if portable_key in portable_expected:
            raise ProfileInstallError(
                f"portable-path collision in release manifest: {portable_expected[portable_key]!r} and {rel!r}"
            )
        portable_expected[portable_key] = rel
        expected[rel] = item
    if value.get("fileCount") not in (None, len(expected)):
        raise ProfileInstallError(
            f"release-manifest fileCount {value.get('fileCount')} != {len(expected)}"
        )
    candidates = [bundle_root, *bundle_root.rglob("*")]
    symlinks = [candidate.relative_to(bundle_root).as_posix() or "." for candidate in candidates if candidate.is_symlink()]
    if symlinks:
        raise ProfileInstallError("release bundle contains symlink(s): " + ", ".join(sorted(symlinks)))
    actual = {
        candidate.relative_to(bundle_root).as_posix()
        for candidate in candidates
        if candidate.is_file() and candidate.name != "RELEASE-MANIFEST.json"
    }
    missing = sorted(set(expected) - actual)
    unexpected = sorted(actual - set(expected))
    errors: list[str] = []
    errors.extend(f"missing: {item}" for item in missing)
    errors.extend(f"unexpected: {item}" for item in unexpected)
    for rel in sorted(set(expected) & actual):
        item = expected[rel]
        candidate = bundle_root / rel
        if item.get("bytes") is not None and candidate.stat().st_size != item.get("bytes"):
            errors.append(f"size mismatch: {rel}")
        if item.get("sha256") and sha256_file(candidate) != item.get("sha256"):
            errors.append(f"digest mismatch: {rel}")
    if errors:
        raise ProfileInstallError("release-bundle verification failed: " + "; ".join(errors))
    return {"status": "PASS", "file_count": len(expected), "manifest": str(path)}


def verify_repository_manifest(repository_root: Path) -> dict[str, Any]:
    """Verify an extracted, Git-friendly language-profile repository."""
    path = repository_root / "REPOSITORY-MANIFEST.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileInstallError(f"invalid repository manifest {path}: {exc}") from exc
    if value.get("schema") != "bbk.language-profiles-repository-manifest.v1":
        raise ProfileInstallError(
            f"unsupported repository-manifest schema {value.get('schema')!r}: {path}"
        )
    if value.get("status") != "PASS":
        raise ProfileInstallError(
            f"language-profile repository is not qualified PASS (status={value.get('status')!r}): {path}"
        )
    records = value.get("profiles")
    if not isinstance(records, list) or not records:
        raise ProfileInstallError(f"repository manifest profiles must be a non-empty list: {path}")

    expected: dict[str, dict[str, Any]] = {}
    seen_ids: dict[str, str] = {}
    seen_paths: dict[str, str] = {}
    for item in records:
        if not isinstance(item, dict):
            raise ProfileInstallError(f"invalid repository profile record: {item!r}")
        profile_id = item.get("id")
        version = item.get("version")
        raw_path = item.get("path")
        root_sha256 = item.get("root_sha256")
        if not isinstance(profile_id, str) or not PROFILE_ID_RE.fullmatch(profile_id):
            raise ProfileInstallError(f"invalid repository profile id: {profile_id!r}")
        if not isinstance(version, str) or not version:
            raise ProfileInstallError(f"invalid repository profile version for {profile_id!r}")
        if not isinstance(raw_path, str):
            raise ProfileInstallError(f"invalid repository profile path for {profile_id!r}")
        rel = _safe_relative(raw_path, label="repository profile path")
        if not rel.parts or rel.parts[0] != "packages":
            raise ProfileInstallError(
                f"repository profile path must be beneath packages/: {raw_path!r}"
            )
        if not isinstance(root_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", root_sha256):
            raise ProfileInstallError(f"invalid repository root digest for {profile_id!r}")
        path_key = rel.as_posix().casefold()
        if path_key in seen_paths:
            raise ProfileInstallError(
                f"portable-path collision in repository manifest: {seen_paths[path_key]!r} and {rel.as_posix()!r}"
            )
        id_key = profile_id.casefold()
        if id_key in seen_ids:
            raise ProfileInstallError(
                f"duplicate profile id in repository manifest: {seen_ids[id_key]!r} and {profile_id!r}"
            )
        seen_paths[path_key] = rel.as_posix()
        seen_ids[id_key] = profile_id
        candidate = repository_root.joinpath(*rel.parts)
        if not candidate.is_dir():
            raise ProfileInstallError(f"repository profile directory is missing: {candidate}")
        expected[rel.as_posix()] = item

    actual = {
        root.relative_to(repository_root).as_posix()
        for root in _profile_roots(repository_root)
    }
    packages_root = repository_root / "packages"
    expected_children = {PurePosixPath(path).parts[1] for path in expected}
    package_children = {child.name for child in packages_root.iterdir()}
    untracked_children = sorted(package_children - expected_children, key=str.casefold)
    if untracked_children:
        raise ProfileInstallError(
            "repository packages/ contains untracked entries: " + ", ".join(untracked_children)
        )
    non_direct_paths = sorted(
        path for path in expected if len(PurePosixPath(path).parts) != 2
    )
    if non_direct_paths:
        raise ProfileInstallError(
            "repository profile paths must be direct packages/ children: "
            + ", ".join(non_direct_paths)
        )
    missing = sorted(set(expected) - actual)
    unexpected = sorted(actual - set(expected))
    if missing or unexpected:
        problems = [*(f"missing: {item}" for item in missing), *(f"unexpected: {item}" for item in unexpected)]
        raise ProfileInstallError("repository profile inventory mismatch: " + "; ".join(problems))
    declared_count = value.get("profile_count")
    if declared_count not in (None, len(expected)):
        raise ProfileInstallError(
            f"repository-manifest profile_count {declared_count} != {len(expected)}"
        )
    return {
        "status": "PASS",
        "manifest": str(path),
        "profile_count": len(expected),
        "records": [expected[key] for key in sorted(expected)],
    }


def _installation_path(profile_root: Path, raw: Any, *, label: str, required: bool = False) -> Path | None:
    if raw is None:
        if required:
            raise ProfileInstallError(f"profile installation is missing {label}")
        return None
    if not isinstance(raw, str):
        raise ProfileInstallError(f"profile installation {label} must be a string")
    rel = _safe_relative(raw, label=f"profile installation {label}")
    target = profile_root.joinpath(*rel.parts)
    if required and not target.is_file():
        raise ProfileInstallError(f"profile installation {label} does not exist: {target}")
    if not required and not target.exists():
        raise ProfileInstallError(f"profile installation {label} does not exist: {target}")
    return target


def prepare_profile_root(
    profile_root: Path,
    *,
    source: str,
    source_sha256: str | None,
    bundle_source: str | None = None,
) -> PreparedProfile:
    try:
        profile = json.loads((profile_root / "PROFILE.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileInstallError(f"invalid PROFILE.json in {profile_root}: {exc}") from exc
    report = validate_profile(profile)
    if not report.get("valid"):
        raise ProfileInstallError(
            f"invalid profile contract in {profile_root}: " + "; ".join(report.get("errors", []))
        )
    profile_id = str(profile.get("id") or "")
    version = str(profile.get("version") or "")
    if not PROFILE_ID_RE.fullmatch(profile_id):
        raise ProfileInstallError(f"invalid profile id: {profile_id!r}")
    if not version:
        raise ProfileInstallError(f"profile version is absent: {profile_root}")
    version_file = profile_root / "VERSION"
    if version_file.is_file() and version_file.read_text(encoding="utf-8").strip() != version:
        raise ProfileInstallError(f"PROFILE.json and VERSION disagree in {profile_root}")

    package = verify_profile_package(profile_root)
    if package.get("status") != "PASS":
        raise ProfileInstallError(
            f"profile package verification failed for {profile_id}@{version}: "
            + "; ".join(package.get("errors", []))
        )
    if package.get("version") and str(package.get("version")) != version:
        raise ProfileInstallError(f"profile package manifest version disagrees for {profile_id}@{version}")
    manifest_name = package.get("name")
    if manifest_name and profile.get("package") and str(manifest_name) != str(profile.get("package")):
        raise ProfileInstallError(f"profile package name disagrees for {profile_id}@{version}")

    installation = profile.get("installation") or {}
    if installation and not isinstance(installation, dict):
        raise ProfileInstallError(f"profile installation contract must be an object: {profile_id}")
    if installation:
        _installation_path(profile_root, installation.get("cli"), label="cli", required=True)
        if installation.get("skill_root") is not None:
            skill_root = _installation_path(profile_root, installation.get("skill_root"), label="skill_root")
            if skill_root is not None and not skill_root.is_dir():
                raise ProfileInstallError(f"profile skill_root is not a directory: {skill_root}")
        if installation.get("omp_extension") is not None:
            extension = _installation_path(profile_root, installation.get("omp_extension"), label="omp_extension")
            if extension is not None and not extension.is_dir():
                raise ProfileInstallError(f"profile omp_extension is not a directory: {extension}")

    compatibility = profile_compatibility(profile)
    if compatibility.get("status") != "PASS":
        raise ProfileInstallError(
            f"profile {profile_id}@{version} is incompatible with this BBK/Python runtime"
        )
    return PreparedProfile(
        root=profile_root.resolve(),
        profile=profile,
        source=source,
        source_sha256=source_sha256,
        package_verification=package,
        compatibility=compatibility,
        bundle_source=bundle_source,
    )


def _prepare_repository(
    repository_root: Path,
    *,
    source_label: str,
    selected_ids: set[str] | None,
    progress: ProgressCallback | None = None,
) -> list[PreparedProfile]:
    report = verify_repository_manifest(repository_root)
    values: list[PreparedProfile] = []
    for index, item in enumerate(report["records"], start=1):
        rel = _safe_relative(str(item["path"]), label="repository profile path")
        _progress(
            progress,
            f"    [{index}/{len(report['records'])}] Verifying extracted profile {item.get('id')}@{item.get('version')}",
        )
        root = repository_root.joinpath(*rel.parts)
        prepared = prepare_profile_root(
            root,
            source=f"{source_label}/{rel.as_posix()}",
            source_sha256=None,
            bundle_source=source_label,
        )
        if prepared.profile_id != item.get("id"):
            raise ProfileInstallError(
                f"repository manifest id disagrees for {rel.as_posix()}: "
                f"{item.get('id')!r} != {prepared.profile_id!r}"
            )
        if prepared.version != item.get("version"):
            raise ProfileInstallError(
                f"repository manifest version disagrees for {prepared.profile_id}: "
                f"{item.get('version')!r} != {prepared.version!r}"
            )
        if prepared.root_sha256 != item.get("root_sha256"):
            raise ProfileInstallError(
                f"repository manifest root digest disagrees for {prepared.profile_id}@{prepared.version}"
            )
        if item.get("package") not in (None, prepared.package_name):
            raise ProfileInstallError(
                f"repository manifest package name disagrees for {prepared.profile_id}@{prepared.version}"
            )
        if selected_ids is None or prepared.profile_id in selected_ids:
            values.append(prepared)
    return values


def _prepare_bundle(
    bundle_root: Path,
    *,
    temp_root: Path,
    source_label: str,
    selected_ids: set[str] | None,
    progress: ProgressCallback | None = None,
) -> list[PreparedProfile]:
    verify_bundle_manifest(bundle_root)
    archives = sorted((bundle_root / "packages").glob("*.zip"))
    if not archives:
        raise ProfileInstallError(f"profile release bundle has no packages/*.zip: {bundle_root}")
    values: list[PreparedProfile] = []
    for index, archive in enumerate(archives):
        _progress(
            progress,
            f"    [{index + 1}/{len(archives)}] Verifying profile archive {archive.name}",
        )
        destination = temp_root / f"bundle-profile-{index:03d}"
        destination.mkdir(parents=True, exist_ok=False)
        safe_extract_zip(archive, destination)
        roots = _profile_roots(destination)
        if len(roots) != 1:
            raise ProfileInstallError(f"profile archive must contain exactly one package root: {archive}")
        prepared = prepare_profile_root(
            roots[0],
            source=f"{source_label}!/{archive.relative_to(bundle_root).as_posix()}",
            source_sha256=sha256_file(archive),
            bundle_source=source_label,
        )
        if selected_ids is None or prepared.profile_id in selected_ids:
            values.append(prepared)
    return values


def _prepare_path(
    source: Path,
    *,
    temp_root: Path,
    sequence: int,
    selected_ids: set[str] | None,
    progress: ProgressCallback | None = None,
) -> list[PreparedProfile]:
    source = source.expanduser().resolve()
    if not source.exists():
        raise ProfileInstallError(f"language-profile source does not exist: {source}")
    if source.is_file():
        if source.suffix.lower() != ".zip":
            raise ProfileInstallError(f"language-profile source must be a ZIP or directory: {source}")
        extracted = temp_root / f"source-{sequence:03d}"
        extracted.mkdir(parents=True, exist_ok=False)
        safe_extract_zip(source, extracted)
        repositories = _repository_roots(extracted)
        bundles = _bundle_roots(extracted)
        profiles = _profile_roots(extracted)
        if repositories:
            if len(repositories) != 1 or bundles:
                raise ProfileInstallError(f"ambiguous ZIP contains multiple profile source layouts: {source}")
            return _prepare_repository(
                repositories[0], source_label=str(source), selected_ids=selected_ids, progress=progress
            )
        if bundles and profiles:
            raise ProfileInstallError(f"ambiguous ZIP contains both bundle and direct profile roots: {source}")
        if len(bundles) == 1:
            return _prepare_bundle(
                bundles[0], temp_root=temp_root, source_label=str(source), selected_ids=selected_ids, progress=progress
            )
        if len(profiles) == 1:
            _progress(progress, f"    [1/1] Verifying extracted profile package {profiles[0].name}")
            prepared = prepare_profile_root(
                profiles[0], source=str(source), source_sha256=sha256_file(source)
            )
            return [prepared] if selected_ids is None or prepared.profile_id in selected_ids else []
        if len(profiles) > 1:
            values = []
            for index, root in enumerate(profiles, start=1):
                _progress(progress, f"    [{index}/{len(profiles)}] Verifying extracted profile package {root.name}")
                values.append(prepare_profile_root(
                    root,
                    source=f"{source}!/{root.relative_to(extracted).as_posix()}",
                    source_sha256=None,
                ))
            return [item for item in values if selected_ids is None or item.profile_id in selected_ids]
        raise ProfileInstallError(f"ZIP is not a profile package, extracted-profile repository, or supported release bundle: {source}")

    repositories = _repository_roots(source)
    bundles = _bundle_roots(source)
    profiles = _profile_roots(source)
    if repositories:
        if len(repositories) != 1 or bundles:
            raise ProfileInstallError(f"ambiguous language-profile directory: {source}")
        return _prepare_repository(
            repositories[0], source_label=str(source), selected_ids=selected_ids, progress=progress
        )
    if len(bundles) == 1 and not profiles:
        return _prepare_bundle(
            bundles[0], temp_root=temp_root, source_label=str(source), selected_ids=selected_ids, progress=progress
        )
    if profiles and not bundles:
        values = []
        for index, root in enumerate(profiles, start=1):
            _progress(progress, f"    [{index}/{len(profiles)}] Verifying extracted profile package {root.name}")
            values.append(prepare_profile_root(root, source=str(root), source_sha256=None))
        return [item for item in values if selected_ids is None or item.profile_id in selected_ids]
    if bundles or profiles:
        raise ProfileInstallError(f"ambiguous language-profile directory: {source}")
    raise ProfileInstallError(f"directory is not a profile package, extracted-profile repository, or release bundle: {source}")


def prepare_profile_sources(
    sources: Sequence[str | os.PathLike[str]],
    *,
    temp_root: Path,
    selected_ids: Sequence[str] | None = None,
    progress: ProgressCallback | None = None,
) -> list[PreparedProfile]:
    """Prepare, verify, select, and deduplicate all supplied profile sources."""
    selected = set(selected_ids or []) or None
    if selected is not None:
        invalid = sorted(value for value in selected if not PROFILE_ID_RE.fullmatch(value))
        if invalid:
            raise ProfileInstallError(f"invalid selected profile id(s): {invalid}")
    values: list[PreparedProfile] = []
    for index, raw in enumerate(sources):
        _progress(progress, f"  Source [{index + 1}/{len(sources)}]: {raw}")
        values.extend(
            _prepare_path(
                Path(raw), temp_root=temp_root, sequence=index,
                selected_ids=selected, progress=progress,
            )
        )
    by_identity: dict[tuple[str, str], PreparedProfile] = {}
    for item in values:
        key = (item.profile_id, item.version)
        previous = by_identity.get(key)
        if previous is not None and previous.root_sha256 != item.root_sha256:
            raise ProfileInstallError(
                f"conflicting packages supplied for {item.profile_id}@{item.version}"
            )
        by_identity[key] = item
    prepared = sorted(by_identity.values(), key=lambda item: (item.profile_id, item.version))
    if selected is not None:
        missing = sorted(selected - {item.profile_id for item in prepared})
        if missing:
            raise ProfileInstallError(f"selected profile id(s) not found: {missing}")
    return prepared


def profile_summary(item: PreparedProfile) -> dict[str, Any]:
    return {
        "id": item.profile_id,
        "version": item.version,
        "name": item.profile.get("name"),
        "package": item.package_name,
        "source": item.source,
        "source_sha256": item.source_sha256,
        "bundle_source": item.bundle_source,
        "root_sha256": item.root_sha256,
        "file_count": item.package_verification.get("file_count"),
        "compatibility": item.compatibility,
    }
