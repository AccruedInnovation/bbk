#!/usr/bin/env python3
"""Offline verifier for the Alpha.17 governed vertical-slice fixture."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED = {
    "backend/result.json": {
        "component": "backend",
        "owner": "bbk_worker",
        "status": "implemented",
        "work_unit": "WU-FIXTURE-BACKEND",
    },
    "frontend/result.json": {
        "component": "frontend",
        "owner": "bbk_worker",
        "status": "implemented",
        "work_unit": "WU-FIXTURE-FRONTEND",
    },
}


def main() -> int:
    observed: dict[str, object] = {}
    for relative, expected in EXPECTED.items():
        path = ROOT / relative
        if not path.is_file() or path.is_symlink():
            raise SystemExit(f"missing safe fixture output: {relative}")
        value = json.loads(path.read_text(encoding="utf-8"))
        if value != expected:
            raise SystemExit(f"fixture output mismatch for {relative}: {value!r}")
        observed[relative] = value
    unexpected = sorted(
        path.relative_to(ROOT).as_posix()
        for directory in (ROOT / "backend", ROOT / "frontend")
        for path in directory.iterdir()
        if path.name not in {"README.md", "result.json"}
    )
    if unexpected:
        raise SystemExit(f"unexpected fixture content: {unexpected}")
    print(json.dumps({"status": "PASS", "verified": sorted(observed)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
