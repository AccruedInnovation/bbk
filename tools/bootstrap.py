#!/usr/bin/env python3
"""Compatibility entry point for ``tools/setup.py``.

Use ``--test``, ``--install``, ``--test-and-install``, ``--update-omp``, or
``--test-and-update-omp``. All remaining flags are forwarded unchanged to the
canonical setup implementation.
"""
from __future__ import annotations

from typing import Sequence

import setup as setup_tool


def main(argv: Sequence[str] | None = None) -> int:
    return setup_tool.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
