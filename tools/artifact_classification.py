"""Shared classification for shipped examples and other non-operational artifacts."""
from __future__ import annotations

import os
from pathlib import Path


def is_non_operational_example(path: str | os.PathLike[str] | Path) -> bool:
    """Return whether ``path`` is a shipped example/template, never live state."""
    return Path(os.fspath(path)).name.casefold().startswith("example-")
