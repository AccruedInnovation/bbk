#!/usr/bin/env python3
"""Compatibility entry point for ``tools/setup.py``.

Use ``--check-dependencies``, ``--install-dependencies``, ``--test-fast``,
``--test``, ``--release-test``, ``--install``, ``--test-and-install``, the
selective OMP/Codex update actions, or their verified forms. All remaining
flags are forwarded unchanged to the canonical setup implementation.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runtime_requirements import enforce_supported_python

enforce_supported_python(program="BBK bootstrap")

import setup as setup_tool


def main(argv: Sequence[str] | None = None) -> int:
    return setup_tool.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
