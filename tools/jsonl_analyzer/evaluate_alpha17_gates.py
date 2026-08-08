#!/usr/bin/env python3
"""Evaluate Alpha.17.0.1 prompt and rolling-wave gates from typed runtime evidence.

Free-form user, developer, assistant, command, and tool-output text never counts
as a behavioral event.  Runtime claims must be represented by schema-bound
objects in ``typed_events.jsonl`` and, where applicable, actual collaboration
calls in ``function_calls.csv``.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

TEST_IDS = {"ALL", "MH-CODEX-01", "MH-CODEX-02", "MH-CODEX-03"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def compact_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _gate(gate_id: str, passed: bool, statement: str, observed: Any, expected: Any) -> dict[str, Any]:
    return {"id": gate_id, "status": "PASS" if passed else "FAIL", "statement": statement, "expected": expected, "observed": observed}


def _catalog_ids(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, dict):
        for key in ("effective_external_catalog", "available_external_procedures", "available", "skills", "procedure_ids"):
            items = value.get(key)
            if isinstance(items, list):
                return [str(item) for item in items]
    raise ValueError("effective catalog must be an array or an object with an array catalog field")


def _csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _typed_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    values: list[dict[str, Any]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not raw.strip():
            continue
        value = json.loads(raw)
        if not isinstance(value, dict) or not isinstance(value.get("schema"), str):
            raise ValueError(f"typed event line {line_no} is not a schema-bound object")
        values.append(value)
    return values


def _prompt_event_valid(event: Mapping[str, Any]) -> bool:
    return (
        event.get("schema") == "bbk.prompt-compilation-event.v1"
        and event.get("event") in {"PROMPT_COMPILED", "PROMPT_REUSED"}
        and isinstance(event.get("logical_child_id"), str) and bool(event.get("logical_child_id"))
        and isinstance(event.get("effective_prompt_sha256"), str) and len(str(event.get("effective_prompt_sha256"))) == 64
        and isinstance(event.get("procedure_ids"), list) and bool(event.get("procedure_ids"))
        and event.get("procedure_reads_by_model") == 0
        and isinstance(event.get("source_reads_by_compiler"), int)
    )


def _required_gate_ids(test_id: str) -> set[str]:
    static = {"A17-CP-PRIMARY-ONCE", "A17-CP-CATALOG-SUPPRESSED", "A17-CP-TYPED-COMPILE", "A17-CP-FILESYSTEM-READS"}
    if test_id == "MH-CODEX-01":
        return static
    if test_id == "MH-CODEX-02":
        return static | {"A17-CP-FOLLOWUP-REUSE"}
    if test_id == "MH-CODEX-03":
        return static | {"A17-RW-FRONTIER-EXECUTION"}
    return static | {"A17-CP-FOLLOWUP-REUSE", "A17-RW-FRONTIER-EXECUTION"}


def evaluate(
    *, analysis_dir: Path, manifest_path: Path, catalog_path: Path,
    readiness_path: Path, prompt_path: Path, test_id: str = "ALL",
) -> dict[str, Any]:
    if test_id not in TEST_IDS:
        raise ValueError(f"unsupported test id: {test_id}")
    summary = load_json(analysis_dir / "summary.json")
    manifest = load_json(manifest_path)
    catalog = _catalog_ids(load_json(catalog_path))
    readiness = load_json(readiness_path)
    prompt = prompt_path.read_text(encoding="utf-8-sig")
    events = _typed_events(analysis_dir / "typed_events.jsonl")
    functions = _csv_rows(analysis_dir / "function_calls.csv")
    skill_rows = _csv_rows(analysis_dir / "skill_reads.csv")

    procedures = [item for item in manifest.get("procedures") or [] if isinstance(item, Mapping)]
    ids = [str(item.get("id")) for item in procedures]
    suppression = [str(item) for item in manifest.get("catalog_suppression_set") or []]
    primary = [str(item.get("id")) for item in procedures if item.get("selection_reason") == "PRIMARY"]
    prompt_marker_counts = {
        proc_id: prompt.count(f"Compiled primary procedure: `{proc_id}`") + prompt.count(f"Compiled procedure: `{proc_id}`")
        for proc_id in ids
    }
    tail_marker = "## End compiled procedures"
    once = (
        bool(ids) and len(ids) == len(set(ids)) and len(primary) == 1 and ids[-1] == primary[0]
        and all(count == 1 for count in prompt_marker_counts.values())
        and prompt.count(tail_marker) == 1 and prompt.rstrip().endswith(tail_marker)
    )
    overlap = sorted(set(ids) & set(catalog))
    catalog_digest = manifest.get("effective_external_catalog_sha256") or compact_digest(catalog)
    catalog_ok = set(ids) == set(suppression) and not overlap and all(item.get("catalog_visibility") == "SUPPRESSED" for item in procedures)

    matching_skill_rows = []
    for row in skill_rows:
        skill = str(row.get("skill") or "").lower()
        if any(skill == proc_id.lower() or proc_id.lower() in skill for proc_id in ids):
            matching_skill_rows.append(row)
    reads_zero = not matching_skill_rows

    compile_events = [event for event in events if _prompt_event_valid(event) and event.get("event") == "PROMPT_COMPILED"]
    matching_compile_events = [
        event for event in compile_events
        if event.get("effective_prompt_sha256") == manifest.get("compiled_prompt_sha256")
        and list(event.get("procedure_ids") or []) == ids
        and event.get("external_catalog_sha256") == catalog_digest
        and event.get("role") == manifest.get("role")
        and event.get("harness") == manifest.get("harness")
        and event.get("reused") is False
        and int(event.get("source_reads_by_compiler") or 0) >= len(ids)
    ]
    compile_ok = bool(matching_compile_events)

    compiled_child_ids = {str(event.get("logical_child_id")) for event in matching_compile_events}
    reuse_events = [
        event for event in events
        if _prompt_event_valid(event) and event.get("event") == "PROMPT_REUSED"
        and event.get("logical_child_id") in compiled_child_ids
        and event.get("effective_prompt_sha256") == manifest.get("compiled_prompt_sha256")
        and list(event.get("procedure_ids") or []) == ids
        and event.get("source_reads_by_compiler") == 0
        and event.get("reused") is True
    ]
    followup_calls = [row for row in functions if row.get("name") == "followup_task"]
    followup_bound = False
    for row in followup_calls:
        raw = row.get("arguments_json") or ""
        if any(child_id and child_id in raw for child_id in compiled_child_ids):
            followup_bound = True
            break
    # Hosts that preserve the same logical child without exposing its ID in the
    # call arguments still require one actual followup_task plus the exact typed
    # PROMPT_REUSED event emitted by the adapter.
    followup_ok = bool(reuse_events) and bool(followup_calls) and (followup_bound or len(compiled_child_ids) == 1)

    readiness_events = [event for event in events if event.get("schema") == "bbk.planning-readiness.v1"]
    readiness_values = {str(item) for item in readiness.get("readiness") or []}
    deferred = readiness.get("deferred_refinements") or []
    future_deferred = bool(deferred) and all(isinstance(item, Mapping) and item.get("status") == "DEFERRED_UNTIL_FRONTIER" for item in deferred)
    matching_readiness = [
        event for event in readiness_events
        if {"ROADMAP_READY", "FRONTIER_READY"}.issubset({str(item) for item in event.get("readiness") or []})
        and event.get("execution_admissible") is True
        and event.get("frontier_ref") == readiness.get("frontier_ref")
        and event.get("deferred_refinements") == deferred
    ]
    worker_events = []
    for event in events:
        if event.get("schema") != "bbk.child-event.v1" or event.get("state") != "STARTED":
            continue
        detail = event.get("detail") if isinstance(event.get("detail"), Mapping) else {}
        role_text = str(detail.get("role") or detail.get("agent_role") or event.get("child_ref") or "").lower()
        if "worker" in role_text:
            worker_events.append(event)
    ordered_worker = False
    for ready in matching_readiness:
        rt = parse_time(ready.get("_timestamp") or ready.get("observed_at"))
        for worker in worker_events:
            wt = parse_time(worker.get("_timestamp") or worker.get("observed_at"))
            if rt is None or wt is None or wt >= rt:
                ordered_worker = True
                break
        if ordered_worker:
            break
    frontier_ok = (
        {"ROADMAP_READY", "FRONTIER_READY"}.issubset(readiness_values)
        and readiness.get("execution_admissible") is True
        and isinstance(readiness.get("frontier_ref"), Mapping)
        and future_deferred and bool(matching_readiness) and bool(worker_events) and ordered_worker
    )

    gates = [
        _gate("A17-CP-PRIMARY-ONCE", once, "Every selected procedure appears exactly once and the primary is the final semantic procedure.", {"marker_counts": prompt_marker_counts, "primary": primary, "tail_final": prompt.rstrip().endswith(tail_marker)}, {"each_marker_count": 1, "one_primary_last": True, "tail_final": True}),
        _gate("A17-CP-CATALOG-SUPPRESSED", catalog_ok, "Compiled procedures are suppressed from the effective external catalog.", {"compiled": ids, "suppression": suppression, "overlap": overlap}, {"overlap": [], "suppression_equals_compiled": True}),
        _gate("A17-CP-TYPED-COMPILE", compile_ok, "A schema-bound runtime compilation event matches the exact prompt, procedure set, role, harness, and catalog.", {"typed_compile_events": len(compile_events), "matching": len(matching_compile_events)}, ">=1 exact matching typed event"),
        _gate("A17-CP-FILESYSTEM-READS", reads_zero, "No model filesystem read of a compiled procedure source occurred.", {"matching_skill_rows": len(matching_skill_rows)}, 0),
        _gate("A17-CP-FOLLOWUP-REUSE", followup_ok, "An actual followup_task reused the same logical child compilation with zero source reads.", {"followup_calls": len(followup_calls), "typed_reuse_events": len(reuse_events), "logical_child_ids": sorted(compiled_child_ids)}, "actual call + exact PROMPT_REUSED event"),
        _gate("A17-RW-FRONTIER-EXECUTION", frontier_ok, "A runtime readiness record admitted Worker execution after ROADMAP_READY + FRONTIER_READY while future work remained deferred.", {"matching_readiness_events": len(matching_readiness), "worker_started_events": len(worker_events), "ordered": ordered_worker, "future_deferred": future_deferred}, "runtime readiness then Worker STARTED"),
    ]
    required = _required_gate_ids(test_id)
    failures = [item["id"] for item in gates if item["id"] in required and item["status"] != "PASS"]
    return {
        "schema": "bbk.alpha17-observability-gate-report.v2",
        "status": "PASS" if not failures else "FAIL",
        "test_id": test_id,
        "analysis_label": summary.get("label"),
        "evidence_policy": "SCHEMA_BOUND_TYPED_EVENTS_ONLY",
        "required_gate_ids": sorted(required),
        "inputs": {"analysis_dir": str(analysis_dir), "compiled_manifest": str(manifest_path), "effective_catalog": str(catalog_path), "planning_readiness": str(readiness_path), "prompt": str(prompt_path)},
        "gates": gates,
        "failed_gate_ids": failures,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument("--compiled-manifest", type=Path, required=True)
    parser.add_argument("--effective-catalog", type=Path, required=True)
    parser.add_argument("--planning-readiness", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--test-id", choices=sorted(TEST_IDS), default="ALL")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = evaluate(analysis_dir=args.analysis_dir.resolve(), manifest_path=args.compiled_manifest.resolve(), catalog_path=args.effective_catalog.resolve(), readiness_path=args.planning_readiness.resolve(), prompt_path=args.prompt.resolve(), test_id=args.test_id)
    write_json(args.output.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
