"""Shared classification for shipped examples and other non-operational artifacts."""
from __future__ import annotations

import os
from pathlib import Path


def is_non_operational_example(path: str | os.PathLike[str] | Path) -> bool:
    """Return whether ``path`` is a shipped example/template, never live state."""
    value = Path(os.fspath(path))
    if value.name.casefold().startswith("example-"):
        return True
    parts = [part.casefold() for part in value.parts]
    return any(parts[index] == ".bbk" and parts[index + 1] == "examples" for index in range(len(parts) - 1))
