#!/usr/bin/env python3
"""Render or verify BBK skills and method references from canonical sources."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from prompt_modules import (  # noqa: E402
    PromptModuleError,
    expand_skill_template,
    load_prompt_modules,
    validate_skill_templates,
)

SPEC = ROOT / "spec" / "method-content.json"


def expected(*, allow_staged: bool = False) -> dict[Path, bytes]:
    data = json.loads(SPEC.read_text(encoding="utf-8"))
    package = load_prompt_modules(ROOT)
    errors = validate_skill_templates(data, package)
    if errors:
        raise PromptModuleError(errors)

    role_catalog = json.loads((ROOT / "spec" / "roles" / "catalog.json").read_text(encoding="utf-8"))
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    source_version = data.get("version")
    if source_version != package.catalog.get("package_version"):
        raise PromptModuleError([
            f"method-content version {source_version} != prompt-module package {package.catalog.get('package_version')}"
        ])
    if source_version != role_catalog.get("package_version"):
        raise PromptModuleError([
            f"method-content version {source_version} != role package {role_catalog.get('package_version')}"
        ])
    if not allow_staged and source_version != version:
        raise PromptModuleError([f"method-content version {source_version} != repository VERSION {version}"])

    values: dict[Path, bytes] = {}
    for name, template in data.get("skills", {}).items():
        expanded = expand_skill_template(template, package)
        values[ROOT / "shared" / "skills" / name / "SKILL.md"] = expanded.encode("utf-8")
    for name, text in data.get("references", {}).items():
        if not isinstance(name, str) or not isinstance(text, str):
            raise PromptModuleError(["method-content references must map string names to string content"])
        values[ROOT / "shared" / "references" / name] = text.encode("utf-8")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--allow-staged",
        action="store_true",
        help="allow staged canonical sources while repository VERSION remains at the prior release during intermediate gates",
    )
    args = parser.parse_args()
    allow_staged = args.allow_staged or os.environ.get("BBK_ALLOW_STAGED_ROLE_PACKAGE") == "1"
    try:
        values = expected(allow_staged=allow_staged)
    except (OSError, json.JSONDecodeError, PromptModuleError) as exc:
        print(f"BBK method-content input error: {exc}", file=sys.stderr)
        return 1

    if args.check:
        errors: list[str] = []
        for path, content in values.items():
            if not path.is_file():
                errors.append(f"missing: {path.relative_to(ROOT)}")
            elif path.read_bytes() != content:
                errors.append(f"drift: {path.relative_to(ROOT)}")
        actual = set((ROOT / "shared" / "skills").glob("*/SKILL.md")) | set(
            (ROOT / "shared" / "references").glob("*.md")
        )
        extra = actual - set(values)
        errors.extend(f"unexpected: {path.relative_to(ROOT)}" for path in sorted(extra))
        if errors:
            print("BBK method-content drift:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        print(
            f"OK: {len(values)} method assets match {SPEC.relative_to(ROOT)} "
            f"with {len(load_prompt_modules(ROOT).modules)} canonical prompt modules"
        )
        return 0

    for path, content in values.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print(
        f"wrote {len(values)} method assets from canonical skill templates and "
        f"{len(load_prompt_modules(ROOT).modules)} prompt modules"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
