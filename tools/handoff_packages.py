#!/usr/bin/env python3
"""Sealed bbk.handoff.v2 package construction and verification."""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from strict_json import load_path
    from artifact_packages import ArtifactPackageError, canonical_json_bytes, seal_draft, verify_package
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from strict_json import load_path
    from artifact_packages import ArtifactPackageError, canonical_json_bytes, seal_draft, verify_package

AUTHORITY_BOUNDARY = (
    "A sealed handoff proves exact package bytes and declared local reference closure. "
    "It does not establish independent validation, parent integration, finding closure, acceptance, deployment, or release."
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def seal_handoff(
    semantic: Mapping[str, Any], sources: Sequence[Mapping[str, Any]], *, output_root: Path,
    revision: str = "1",
) -> dict[str, Any]:
    output_root = output_root.expanduser().absolute()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    package_id = str(semantic["id"])
    subject = semantic["subject"]
    with tempfile.TemporaryDirectory(prefix="bbk-handoff-", dir=str(output_root.parent)) as raw:
        draft = Path(raw)
        _write_json(draft / "handoff.json", semantic)
        artifacts: list[dict[str, Any]] = [{
            "artifactId": "handoff", "path": "handoff.json", "schema": "bbk.handoff.v2",
            "role": "result", "references": [str(item["artifactId"]) for item in sources],
        }]
        for item in sources:
            source = Path(str(item["sourcePath"])).resolve(strict=True)
            destination = draft / str(item["packagePath"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            artifacts.append({
                "artifactId": item["artifactId"], "path": item["packagePath"],
                "role": item["role"], "references": [],
                **({"mediaType": item["mediaType"]} if item.get("mediaType") else {}),
            })
        _write_json(draft / "bbk-package-draft.json", {
            "schema": "bbk.artifact-package-draft.v1", "packageId": package_id,
            "revision": revision, "profile": {"id": "handoff-v2", "version": "1"},
            "subject": subject, "predecessor": None, "artifacts": artifacts,
            "metadata": {"authorityBoundary": AUTHORITY_BOUNDARY, "compiler": "tools/handoff_packages.py"},
        })
        return seal_draft(draft, output_root)


def handoff_value(package_root: Path) -> dict[str, Any]:
    package_root = package_root.expanduser().resolve(strict=True)
    manifest = load_path(package_root / "bbk-package-manifest.json")
    if not isinstance(manifest, dict):
        raise ValueError("handoff package manifest is invalid")
    matches = [item for item in manifest.get("artifacts", []) if isinstance(item, dict) and item.get("schema") == "bbk.handoff.v2"]
    if len(matches) != 1:
        raise ValueError("handoff package must contain exactly one bbk.handoff.v2 artifact")
    value = load_path(package_root / str(matches[0]["path"]))
    if not isinstance(value, dict):
        raise ValueError("handoff semantic record is invalid")
    return value


def verify_handoff_package(package_root: Path) -> dict[str, Any]:
    package_root = package_root.expanduser().resolve(strict=True)
    verification = verify_package(package_root)
    errors = [item.get("message", str(item)) for item in verification.get("findings", []) if isinstance(item, dict) and item.get("severity") == "ERROR"]
    value: dict[str, Any] | None = None
    package: dict[str, Any] | None = None
    manifest: dict[str, Any] | None = None
    if verification.get("status") == "PASS":
        try:
            value = handoff_value(package_root)
            package = load_path(package_root / "bbk-package.json")
            manifest = load_path(package_root / "bbk-package-manifest.json")
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    references: list[dict[str, Any]] = []
    if isinstance(manifest, dict):
        by_id = {item.get("artifactId"): item for item in manifest.get("artifacts", []) if isinstance(item, dict)}
        for field in ("artifacts", "evidence"):
            for index, ref in enumerate(value.get(field, []) if isinstance(value, dict) else []):
                item = by_id.get(ref.get("artifactId")) if isinstance(ref, dict) else None
                references.append({"field": field, "index": index, "status": "PASS" if item else "MISSING", **(item or {"artifactId": ref.get("artifactId") if isinstance(ref, dict) else None})})
                if item is None:
                    errors.append(f"{field}[{index}] does not bind a package artifact")
    valid = verification.get("status") == "PASS" and not errors and isinstance(value, dict) and isinstance(package, dict)
    content_sha = package.get("contentSha256") if isinstance(package, dict) else None
    return {
        "schema": "bbk.handoff-verification.v2", "status": "PASS" if valid else "FAIL", "valid": valid,
        "handoff": {
            "path": str(package_root), "bytes": (package_root / "bbk-package.json").stat().st_size if (package_root / "bbk-package.json").is_file() else 0,
            "sha256": content_sha, "contentSha256": content_sha,
            "id": value.get("id") if isinstance(value, dict) else None,
            "work_unit_id": value.get("work_unit_id") if isinstance(value, dict) else None,
            "attempt": value.get("attempt") if isinstance(value, dict) else None,
            "disposition": value.get("disposition") if isinstance(value, dict) else None,
            "smallest_next_action": value.get("smallest_next_action") if isinstance(value, dict) else None,
            "created_at": value.get("created_at") if isinstance(value, dict) else None,
            "producer_role": (value.get("producer") or {}).get("role") if isinstance(value, dict) else None,
            "continuation": value.get("continuation") if isinstance(value, dict) else None,
            "format": "SEALED_V2",
        },
        "references": references, "errors": errors, "packageVerification": verification,
        "authorityBoundary": AUTHORITY_BOUNDARY,
    }
