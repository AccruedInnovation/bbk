#!/usr/bin/env python3
"""Thin compatibility entry point for the canonical BBK artifact package engine."""
from __future__ import annotations

try:
    from artifact_packages import main
except ModuleNotFoundError:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from artifact_packages import main


if __name__ == "__main__":
    raise SystemExit(main())
