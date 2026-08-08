#!/usr/bin/env python3
"""Validate final BBK controller/role prompt semantics across every projection."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from compiled_procedures import load_registry  # noqa: E402
from generate_agents import (  # noqa: E402
    TARGETS, compiled_controller, compiled_instruction,
)
from model_routing import load_model_routing, route_for_role  # noqa: E402

REPORT_PATH = ROOT / "PROMPT-COMPILATION-REPORT.json"
FORBIDDEN_PHRASES = (
    "Commission one exact Phase Wayfinder charter for every non-atomic executable phase",
    "For every work unit define at least",
    "Run the recursive loop",
    "same-attempt repair/retry is prohibited",
    "required after every change",
)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def lint_result(
    *, identity: str, target: str, primary: str, result: Any,
    dependencies: Mapping[str, list[str]], required_phrases: Iterable[str] = (),
) -> list[dict[str, Any]]:
    prompt = result.prompt
    procedures = list(result.manifest.get("procedures") or [])
    ids = [str(item.get("id")) for item in procedures]
    errors: list[dict[str, Any]] = []

    def fail(code: str, detail: Any) -> None:
        errors.append({"code": code, "identity": identity, "target": target, "detail": detail})

    if prompt.count("## End compiled procedures") != 1 or not prompt.rstrip().endswith("## End compiled procedures"):
        fail("TAIL_NOT_FINAL", prompt[-240:])
    if len(ids) != len(set(ids)):
        fail("DUPLICATE_PROCEDURE_ID", ids)
    if not ids or ids[-1] != primary:
        fail("PRIMARY_NOT_LAST", {"primary": primary, "ordered": ids})
    for procedure_id in ids:
        count = prompt.count(f"Compiled primary procedure: `{procedure_id}`") + prompt.count(f"Compiled procedure: `{procedure_id}`")
        if count != 1:
            fail("PROCEDURE_MARKER_COUNT", {"id": procedure_id, "count": count})
    overlap = sorted(set(ids) & set(result.external_catalog))
    if overlap:
        fail("COMPILED_EXTERNAL_OVERLAP", overlap)
    positions = {item: ids.index(item) for item in ids}
    for owner in ids:
        for dependency in dependencies.get(owner, []):
            if dependency not in positions:
                fail("MISSING_DEPENDENCY", {"owner": owner, "dependency": dependency})
            elif positions[dependency] >= positions[owner]:
                fail("DEPENDENCY_ORDER", {"owner": owner, "dependency": dependency, "ordered": ids})
    for section in result.source_map:
        start, end = int(section["start"]), int(section["end"])
        if not (0 <= start <= end <= len(prompt)):
            fail("SOURCE_MAP_RANGE", section)
            continue
        if str(section.get("id", "")).startswith("procedure:"):
            observed = sha256_text(prompt[start:end].rstrip() + "\n")
            if observed != section.get("sha256"):
                fail("SOURCE_MAP_DIGEST", {"section": section, "observed": observed})
    for phrase in FORBIDDEN_PHRASES:
        if phrase.lower() in prompt.lower():
            fail("LEGACY_CONTRADICTION", phrase)
    for phrase in required_phrases:
        if phrase not in prompt:
            fail("REQUIRED_POLICY_MISSING", phrase)
    return errors


def build_report(root: Path = ROOT) -> dict[str, Any]:
    spec = json.loads((root / "spec" / "roles.json").read_text(encoding="utf-8"))
    routing = load_model_routing(root / "spec" / "model-routing.json", root=root, role_spec=spec)
    registry = load_registry(root)
    dependencies = {
        str(item["id"]): [str(value) for value in item.get("procedure_dependencies") or []]
        for item in registry["procedures"]
    }
    errors: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    semantic_sets: dict[str, dict[str, list[str]]] = {}

    for role in sorted(spec["roles"], key=lambda value: value["name"]):
        route = route_for_role(routing, role["name"])
        per_target: dict[str, list[str]] = {}
        required: list[str] = []
        if role["name"] == "bbk_worker":
            required = ["exactly four blocking facts", "CONTAINED_AUTHORITY_INCIDENT"]
        elif role["name"] in {"bbk_root_orchestrator", "bbk_territory_orchestrator", "bbk_worker_orchestrator"}:
            required = ["active-child effect ownership", "CONTAINED_AUTHORITY_INCIDENT"]
        elif role["name"] in {"bbk_root_wayfinder", "bbk_territory_wayfinder"}:
            required = ["FRONTIER_READY", "ARCHITECTURAL_BRANCH"]
        for target in TARGETS:
            result = compiled_instruction(spec, role, host=target, route=route)
            ids = [str(item["id"]) for item in result.manifest["procedures"]]
            per_target[target] = ids
            item_errors = lint_result(
                identity=role["name"], target=target,
                primary=str(role["primary_skill"]), result=result,
                dependencies=dependencies, required_phrases=required,
            )
            errors.extend(item_errors)
            records.append({
                "identity": role["name"], "identity_kind": "ROLE", "target": target,
                "prompt_sha256": result.manifest["compiled_prompt_sha256"],
                "prompt_characters": len(result.prompt), "procedures": ids,
                "external_catalog": list(result.external_catalog), "errors": len(item_errors),
            })
        semantic_sets[role["name"]] = per_target

    controller_sets: dict[str, list[str]] = {}
    for target in TARGETS:
        result = compiled_controller(spec, host=target)
        ids = [str(item["id"]) for item in result.manifest["procedures"]]
        controller_sets[target] = ids
        item_errors = lint_result(
            identity="bbk_controller", target=target, primary="bbk", result=result,
            dependencies=dependencies,
            required_phrases=["MAJOR_BLOCKER", "ARCHITECTURAL_BRANCH", "active-child effect ownership"],
        )
        errors.extend(item_errors)
        records.append({
            "identity": "bbk_controller", "identity_kind": "CONTROLLER", "target": target,
            "prompt_sha256": result.manifest["compiled_prompt_sha256"],
            "prompt_characters": len(result.prompt), "procedures": ids,
            "external_catalog": list(result.external_catalog), "errors": len(item_errors),
        })

    for identity, values in {**semantic_sets, "bbk_controller": controller_sets}.items():
        distinct = {tuple(items) for items in values.values()}
        if len(distinct) != 1:
            errors.append({"code": "CROSS_TARGET_PROCEDURE_DRIFT", "identity": identity, "detail": values})

    return {
        "schema": "bbk.prompt-compilation-lint-report.v1",
        "package_version": spec["package_version"],
        "status": "PASS" if not errors else "FAIL",
        "targets": list(TARGETS),
        "identity_count": len(spec["roles"]) + 1,
        "projection_count": len(records),
        "records": records,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    report = build_report(ROOT)
    payload = canonical(report)
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != payload:
            print(f"prompt compilation report drift: {args.output}", file=sys.stderr)
            return 1
    else:
        args.output.write_bytes(payload)
    print(f"BBK prompt compilation lint: {report['status']} — {report['projection_count']} projections, {len(report['errors'])} errors")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
