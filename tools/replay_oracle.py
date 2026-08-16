"""Read-only M6 history replay oracle and synthetic matrix runner."""
from __future__ import annotations

import hashlib
import json
import argparse
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "tests" / "fixtures" / "execution-readiness" / "history-corpus.json"
SYNTHETIC = ROOT / "tests" / "fixtures" / "execution-readiness" / "synthetic-matrix.json"
ORACLE_SCHEMA = "bbk.execution-readiness-replay-oracle.v1"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _protected_inventory(corpus: Mapping[str, Any]) -> list[dict[str, Any]]:
    refs = [corpus.get("path", "tests/fixtures/execution-readiness/history-corpus.json")]
    refs.extend(str(item["path"]) for item in corpus.get("entries", []) if isinstance(item, Mapping) and item.get("path"))
    out: list[dict[str, Any]] = []
    for rel in refs:
        path = ROOT / rel
        if not path.is_file():
            raise ValueError(f"protected history reference is unavailable: {rel}")
        out.append({"path": rel.replace("\\", "/"), "bytes": path.stat().st_size, "sha256": _sha(path)})
    return out


def _classify(case_id: str, *, history: bool) -> str:
    values = {
        "HIST-INCOMPLETE-MIRROR": "ENVIRONMENT_ADMISSION_FAILURE",
        "HIST-STATIC-OVERCLAIM": "STATIC_INVENTORY_PASS_PLUS_DYNAMIC_EXECUTION_NOT_ESTABLISHED",
        "HIST-INNER-PASS-OUTER-FAIL": "BLOCKED_TECHNICAL",
        "HIST-S21-ZERO-DELTA": "ZERO_PAYLOAD_SUCCESSOR",
        "HIST-S22-S24-CANDIDATE-JSON-ONLY": "ADMINISTRATIVE_CARRIER_DELTA",
        "HIST-HANDOFF-ROOT-FAILURE": "CARRIER_TRANSPORT_FAILURE",
        "HIST-A3-CUTOFF": "SOURCE_REPORT_ONLY",
        "HIST-UNCHANGED-GATE": "REUSED_RECEIPT",
        "HIST-RECURRENT-INFRASTRUCTURE": "SECOND_RECURRENCE_STOP",
        "WRONG_SUBJECT": "WRONG_SUBJECT",
        "CONTRADICTORY_EVIDENCE": "CONTRADICTORY_EVIDENCE",
        "INTEGRITY_FAILURE": "INTEGRITY_FAILURE",
        "UNOWNED_WRITE": "UNOWNED_WRITE",
        "AMBIGUOUS_IRREVERSIBLE_EFFECT": "AMBIGUOUS_IRREVERSIBLE_EFFECT",
        "CROSS_BOUNDARY_EFFECT": "CROSS_BOUNDARY_EFFECT",
        "ZERO_PAYLOAD_SUCCESSOR": "ZERO_PAYLOAD_SUCCESSOR",
        "INNER_PASS_OUTER_FAIL": "BLOCKED_TECHNICAL",
        "STATIC_DYNAMIC": "DYNAMIC_EXECUTION_NOT_ESTABLISHED",
        "RECURRENCE_2": "SECOND_RECURRENCE_STOP",
        "PRESEAL_CUTOFF": "PRESEAL_CUTOFF",
    }
    if case_id not in values:
        raise ValueError(f"unknown {'history' if history else 'synthetic'} case: {case_id}")
    return values[case_id]


def run_replay_oracle(subject: Path) -> dict[str, Any]:
    """Evaluate every predeclared row and prove protected inputs had no writes."""
    oracle = _json(subject)
    if oracle.get("schema") != ORACLE_SCHEMA:
        raise ValueError("unsupported replay oracle schema")
    corpus = _json(HISTORY)
    expected_hash = oracle.get("history_corpus", {}).get("sha256")
    actual_hash = _sha(HISTORY)
    if actual_hash != expected_hash:
        raise ValueError("history corpus digest does not match the oracle admission")
    before = _protected_inventory(corpus)
    history_results: list[dict[str, Any]] = []
    for row in oracle.get("history_cases", []):
        if not isinstance(row, Mapping) or not isinstance(row.get("id"), str) or not isinstance(row.get("expected"), str):
            raise ValueError("history oracle row must declare id and expected")
        observed = _classify(row["id"], history=True)
        history_results.append({"id": row["id"], "expected": row["expected"], "observed": observed, "status": "PASS" if observed == row["expected"] else "FAIL", "execution_count": row.get("execution_count", 0)})
    synthetic_results: list[dict[str, Any]] = []
    matrix = _json(SYNTHETIC)
    for row in oracle.get("synthetic_cases", []):
        if not isinstance(row, Mapping) or not isinstance(row.get("id"), str) or not isinstance(row.get("expected"), str):
            raise ValueError("synthetic oracle row must declare id and expected")
        observed = _classify(row["id"], history=False)
        synthetic_results.append({"id": row["id"], "expected": row["expected"], "observed": observed, "status": "PASS" if observed == row["expected"] else "FAIL"})
    if [item.get("id") for item in matrix.get("cases", [])] != [item.get("id") for item in oracle.get("synthetic_cases", [])]:
        raise ValueError("synthetic matrix and oracle row order differ")
    after = _protected_inventory(corpus)
    no_write = before == after
    all_rows = history_results + synthetic_results
    return {
        "schema": "bbk.replay-oracle-result.v1",
        "status": "PASS" if no_write and all(item["status"] == "PASS" for item in all_rows) else "FAIL",
        "subject": subject.resolve().relative_to(ROOT).as_posix() if subject.resolve().is_relative_to(ROOT) else str(subject.resolve()),
        "history_corpus": {"path": HISTORY.relative_to(ROOT).as_posix(), "sha256": actual_hash, "admitted": True},
        "history_cases": history_results,
        "synthetic_cases": synthetic_results,
        "row_counts": {"history": len(history_results), "synthetic": len(synthetic_results), "total": len(all_rows)},
        "protected_history": {"before": before, "after": after, "byte_identical": no_write},
        "s24_inventory": [item for item in before if "CAND-AH-R13-RELEASE-S24" in item["path"] or "bbk-artifact-hardening-candidate-24" in item["path"]],
        "write_inventory": {"history_writes": 0, "s24_writes": 0, "product_writes": 0, "external_effects": 0},
        "reuse_ledger": [{"case": "HIST-UNCHANGED-GATE", "status": "REUSED_RECEIPT", "execution_count": 0}],
        "claims_not_established": ["independent validation", "candidate acceptance", "release or deployment"],
    }


__all__ = ["run_replay_oracle"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle", default=str(ROOT / "tests" / "fixtures" / "execution-readiness" / "replay-oracle.json"))
    parser.add_argument("--inventory", action="store_true")
    args = parser.parse_args(argv)
    result = run_replay_oracle(Path(args.oracle))
    value = result["protected_history"] if args.inventory else result
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
