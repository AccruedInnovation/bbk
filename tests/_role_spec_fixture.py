"""Minimal isolated source tree for role/prompt package mutation tests."""

from __future__ import annotations

import shutil
from pathlib import Path


def materialize_role_assembly_fixture(
    source_root: Path,
    target_root: Path,
    include_projection: bool = False,
) -> list[Path]:
    """Copy the exact role-assembly closure into an independent writable tree."""

    source_root = Path(source_root).resolve()
    target_root = Path(target_root).resolve()
    spec_root = target_root / "spec"
    spec_root.mkdir(parents=True, exist_ok=True)

    files = [
        source_root / "spec" / "method-content.json",
        source_root / "spec" / "roles" / "catalog.json",
        *sorted((source_root / "spec" / "roles").glob("bbk_*-role.json")),
        source_root / "spec" / "prompt-modules" / "catalog.json",
        *sorted((source_root / "spec" / "prompt-modules").glob("bbk-prompt-*.json")),
        source_root / "spec" / "schemas" / "bbk-role-v4.schema.json",
        source_root / "spec" / "schemas" / "bbk-role-catalog-v4.schema.json",
        source_root / "spec" / "schemas" / "bbk-roles-v4.schema.json",
        source_root / "spec" / "contracts" / "catalog.json",
    ]
    if include_projection:
        files.append(source_root / "spec" / "roles.json")

    copied: list[Path] = []
    for source in files:
        relative = source.relative_to(source_root)
        destination = target_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(destination)
    return copied
