#!/usr/bin/env python3
"""Verify a BBK package tree against PACKAGE-MANIFEST.json."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runtime_requirements import enforce_supported_python

enforce_supported_python(program='BBK package verifier')

EXCLUDED_PARTS = {".git", ".bbk", "evidence", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
INCLUDED_EVIDENCE_FILES = frozenset({
    "evidence/alpha17-rc6-work-unit-dispositions.json",
    "evidence/qualification/deepseek-codex-provider-seam-r4/qualification-receipt.json",
    "evidence/qualification/omp-host-contract-rc9.json",
    "evidence/qualification/session-inspector-oracle-alpha17.json",
})
EXCLUDED_ROOT_FILES = frozenset({"candidate.json"})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def actual_files(root: Path) -> set[str]:
    values: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if (any(part in EXCLUDED_PARTS for part in rel.parts) and rel.as_posix() not in INCLUDED_EVIDENCE_FILES) or path.suffix in EXCLUDED_SUFFIXES:
            continue
        if rel.as_posix() == "PACKAGE-MANIFEST.json" or rel.as_posix() in EXCLUDED_ROOT_FILES:
            continue
        values.add(rel.as_posix())
    return values


def verify(root: Path, *, strict_mode: bool = False) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = root / "PACKAGE-MANIFEST.json"
    if not manifest_path.is_file():
        return {"schema": "bbk.package-verification.v1", "status": "FAIL", "root": str(root), "errors": [f"missing {manifest_path}"]}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"schema": "bbk.package-verification.v1", "status": "FAIL", "root": str(root), "errors": [f"invalid manifest: {exc}"]}
    errors: list[str] = []
    expected = {item["path"]: item for item in manifest.get("files", [])}
    actual = actual_files(root)
    for rel in sorted(set(expected) - actual):
        errors.append(f"missing: {rel}")
    for rel in sorted(actual - set(expected)):
        errors.append(f"unexpected: {rel}")
    for rel in sorted(actual & set(expected)):
        path = root / rel
        item = expected[rel]
        size = path.stat().st_size
        digest = sha256_file(path)
        executable = bool(path.stat().st_mode & 0o111)
        if size != item.get("bytes"):
            errors.append(f"size mismatch: {rel} expected={item.get('bytes')} actual={size}")
        if digest != item.get("sha256"):
            errors.append(f"digest mismatch: {rel} expected={item.get('sha256')} actual={digest}")
        if strict_mode and sys.platform != "win32" and executable != bool(item.get("executable")):
            errors.append(f"executable-bit mismatch: {rel} expected={item.get('executable')} actual={executable}")
    payload = {"schema": "bbk.package-root.v1", "name": manifest.get("name"), "version": manifest.get("version"), "files": manifest.get("files", [])}
    root_digest = hashlib.sha256(canonical(payload)).hexdigest()
    if root_digest != manifest.get("root_sha256"):
        errors.append(f"root digest mismatch: expected={manifest.get('root_sha256')} actual={root_digest}")
    if manifest.get("file_count") != len(expected):
        errors.append(f"file_count mismatch: field={manifest.get('file_count')} records={len(expected)}")
    return {
        "schema": "bbk.package-verification.v1", "status": "PASS" if not errors else "FAIL",
        "root": str(root), "version": manifest.get("version"), "root_sha256": root_digest,
        "file_count": len(expected), "targets": manifest.get("targets", []), "errors": errors,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict-mode", action="store_true")
    args = parser.parse_args(argv)
    result = verify(Path(args.root), strict_mode=args.strict_mode)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(f"BBK package verification: {result['status']}")
        print(f"Root: {result.get('root')}")
        print(f"Version: {result.get('version')}")
        print(f"Files: {result.get('file_count')}")
        print(f"Root SHA-256: {result.get('root_sha256')}")
        for error in result.get("errors", []):
            print(f"- {error}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
