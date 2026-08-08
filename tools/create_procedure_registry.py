#!/usr/bin/env python3
"""Write or verify the canonical BBK compiled-procedure registry."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
from compiled_procedures import canonical_json_bytes, build_registry, REGISTRY_PATH  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = canonical_json_bytes(build_registry(ROOT))
    if args.check:
        if not REGISTRY_PATH.is_file() or REGISTRY_PATH.read_bytes() != expected:
            print(f"procedure registry drift: {REGISTRY_PATH}", file=sys.stderr)
            return 1
        print(f"OK: {REGISTRY_PATH.relative_to(ROOT)} matches canonical method/role sources")
        return 0
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_bytes(expected)
    print(f"wrote {REGISTRY_PATH.relative_to(ROOT)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
