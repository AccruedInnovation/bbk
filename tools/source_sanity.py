#!/usr/bin/env python3
"""Compile package Python sources and parse package JSON without mutating sources."""
from __future__ import annotations

import argparse
import ast
import json
import py_compile
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runtime_requirements import enforce_supported_python

enforce_supported_python(program="BBK source sanity check")

EXCLUDED_PARTS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def package_files() -> list[Path]:
    values: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in rel.parts) or path.suffix in EXCLUDED_SUFFIXES:
            continue
        values.append(path)
    return sorted(values, key=lambda value: value.relative_to(ROOT).as_posix())


def text_encoding_violations(path: Path) -> list[str]:
    """Return Path.read_text/write_text calls that omit an explicit encoding."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError):
        # Compilation reports syntax and I/O failures separately.
        return []
    violations: list[str] = []
    try:
        display_path = path.relative_to(ROOT).as_posix()
    except ValueError:
        display_path = path.as_posix()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"read_text", "write_text"}:
            continue
        if any(keyword.arg == "encoding" for keyword in node.keywords):
            continue
        violations.append(f"{display_path}:{node.lineno}: {node.func.attr}() omits encoding")
    return violations


def validate() -> dict[str, Any]:
    files = package_files()
    python_files = [path for path in files if path.suffix == ".py"]
    json_files = [path for path in files if path.suffix == ".json"]
    errors: list[str] = []
    encoding_violations: list[str] = []
    with tempfile.TemporaryDirectory(prefix="bbk-pycompile-") as raw:
        target_root = Path(raw)
        for path in python_files:
            rel = path.relative_to(ROOT)
            target = target_root / rel.with_suffix(".pyc")
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                py_compile.compile(str(path), cfile=str(target), doraise=True)
            except py_compile.PyCompileError as exc:
                errors.append(f"python compile failed: {rel.as_posix()}: {exc.msg}")
            except OSError as exc:
                errors.append(f"python compile I/O failed: {rel.as_posix()}: {exc}")
    for path in python_files:
        encoding_violations.extend(text_encoding_violations(path))
    errors.extend(f"implicit text encoding: {item}" for item in encoding_violations)
    for path in json_files:
        rel = path.relative_to(ROOT)
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"JSON parse failed: {rel.as_posix()}: {exc}")
    return {
        "schema": "bbk.source-sanity.v1",
        "status": "PASS" if not errors else "FAIL",
        "root": ROOT.as_posix(),
        "python_files": len(python_files),
        "json_files": len(json_files),
        "explicit_text_encoding_calls_checked": len(python_files),
        "implicit_text_encoding_calls": len(encoding_violations),
        "errors": errors,
    }


def human(value: dict[str, Any]) -> str:
    lines = [
        f"BBK source sanity: {value['status']}",
        f"Python files compiled: {value['python_files']}",
        f"JSON files parsed: {value['json_files']}",
        f"Implicit Path text encodings: {value['implicit_text_encoding_calls']}",
    ]
    lines.extend(f"- {error}" for error in value["errors"])
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    value = validate()
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) if args.json else human(value))
    return 0 if value["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
