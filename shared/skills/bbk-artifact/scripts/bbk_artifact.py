#!/usr/bin/env python3
"""Locate an installed BBK package and invoke its JSON artifact CLI.

This script is deliberately small and dependency-free. It supports project- and
user-scope BBK installations without requiring ``bbk`` on PATH.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "bbk.artifact-skill-binding.v1"
MANIFEST_SCHEMA = "bbk.install-manifest.v1"


def _canonical(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _dedupe(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        candidate = _canonical(path)
        key = os.path.normcase(str(candidate))
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return result


def _user_install_root() -> Path:
    override = os.environ.get("BBK_INSTALL_ROOT")
    if override:
        return _canonical(Path(override))
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return _canonical(Path(base) / "BBK")
        return _canonical(Path.home() / "AppData" / "Local" / "BBK")
    if sys.platform == "darwin":
        return _canonical(Path.home() / "Library" / "Application Support" / "BBK")
    base = os.environ.get("XDG_DATA_HOME")
    return _canonical((Path(base).expanduser() if base else Path.home() / ".local" / "share") / "bbk")


def _project_manifests() -> list[Path]:
    result: list[Path] = []
    current = _canonical(Path.cwd())
    while True:
        result.append(current / ".bbk-kit-install.json")
        parent = current.parent
        if parent == current:
            break
        current = parent
    return result


def _manifest_candidates() -> list[Path]:
    candidates: list[Path] = []
    explicit = os.environ.get("BBK_INSTALL_MANIFEST")
    if explicit:
        candidates.append(Path(explicit))
    candidates.extend(_project_manifests())
    candidates.append(_user_install_root() / "install-manifest.json")
    return _dedupe(candidates)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _valid_package_root(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / "VERSION").is_file()
        and (path / "tools" / "bbk.py").is_file()
        and (path / "spec" / "contracts" / "artifact-package-profile-registry.json").is_file()
    )


def _binding_from_root(root: Path, *, source: str, manifest: Path | None = None, python: str | None = None) -> dict[str, Any] | None:
    root = _canonical(root)
    if not _valid_package_root(root):
        return None
    script = _canonical(root / "tools" / "bbk.py")
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    selected_python = python if python and Path(python).is_file() else sys.executable
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "source": source,
        "manifest": str(manifest) if manifest else None,
        "package_root": str(root),
        "version": version,
        "python": str(_canonical(Path(selected_python))),
        "script": str(script),
        "bbk_on_path_required": False,
    }


def _binding_from_manifest(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = _read_json(path)
    if not isinstance(value, dict) or value.get("schema") != MANIFEST_SCHEMA:
        return None
    raw_root = value.get("package_root")
    if not isinstance(raw_root, str) or not raw_root:
        return None

    python: str | None = None
    registry = value.get("language_profile_registry")
    if isinstance(registry, dict):
        cli = registry.get("bbk_cli")
        if isinstance(cli, dict):
            raw_python = cli.get("python")
            if isinstance(raw_python, str) and raw_python:
                python = raw_python
            raw_script = cli.get("script")
            if isinstance(raw_script, str) and raw_script:
                expected = _canonical(Path(raw_root) / "tools" / "bbk.py")
                if _canonical(Path(raw_script)) != expected:
                    return None

    return _binding_from_root(
        Path(raw_root),
        source="install-manifest",
        manifest=path,
        python=python,
    )


def resolve_binding() -> tuple[dict[str, Any] | None, list[str]]:
    checked: list[str] = []

    explicit_root = os.environ.get("BBK_PACKAGE_ROOT")
    if explicit_root:
        checked.append(f"BBK_PACKAGE_ROOT={explicit_root}")
        binding = _binding_from_root(Path(explicit_root), source="BBK_PACKAGE_ROOT")
        if binding:
            return binding, checked

    for manifest in _manifest_candidates():
        checked.append(str(manifest))
        binding = _binding_from_manifest(manifest)
        if binding:
            return binding, checked

    install_root = _user_install_root()
    current_path = install_root / "current.json"
    checked.append(str(current_path))
    current = _read_json(current_path)
    if isinstance(current, dict) and isinstance(current.get("path"), str):
        binding = _binding_from_root(Path(current["path"]), source="current-install", manifest=current_path)
        if binding:
            return binding, checked

    return None, checked


def _failure(checked: list[str]) -> int:
    result = {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "code": "BBK_INSTALLATION_NOT_RESOLVED",
        "message": "No valid BBK installation binding was found; the short bbk command was not required or used.",
        "checked": checked,
        "smallest_next_action": (
            "Confirm the BBK install manifest or BBK_PACKAGE_ROOT, or read "
            "bbk-installed-profiles/SKILL.md for the installation-bound Python/script fallback."
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
    return 127


def _run(binding: dict[str, Any], arguments: list[str]) -> int:
    python = str(binding["python"])
    script = str(binding["script"])
    command = [python, "-B", "-X", "utf8", script, "--json", "artifact", *arguments]
    try:
        completed = subprocess.run(command, check=False)
    except OSError as exc:
        result = {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "code": "BBK_INVOCATION_FAILED",
            "message": str(exc),
            "binding": binding,
            "smallest_next_action": "Repair the exact recorded Python or BBK script path and retry.",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 127
    return int(completed.returncode)


def main(argv: list[str]) -> int:
    binding, checked = resolve_binding()
    if binding is None:
        return _failure(checked)
    if argv and argv[0] == "binding":
        print(json.dumps(binding, ensure_ascii=False, indent=2))
        return 0
    arguments = argv or ["--help"]
    return _run(binding, arguments)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
