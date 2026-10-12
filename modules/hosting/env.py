"""Minimal ``.env`` loader (no external dependencies).

Reads the first ``.env`` found while walking up from the current directory and
from the package directory, and copies its values into ``os.environ``. Real
environment variables always win over the file (``setdefault``), so a CI/VPS
setup can override anything.
"""

from __future__ import annotations

import os
from pathlib import Path


def _parse(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, val = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key:
            values[key] = val
    return values


def _candidates() -> list[Path]:
    seen: list[Path] = []
    for base in (Path.cwd().resolve(), Path(__file__).resolve().parent):
        for parent in (base, *base.parents):
            candidate = parent / ".env"
            if candidate not in seen:
                seen.append(candidate)
    return seen


def load_dotenv(override: bool = False) -> dict[str, str]:
    """Load the first ``.env`` found. Returns the values that were read."""
    for path in _candidates():
        if path.is_file():
            values = _parse(path.read_text(encoding="utf-8"))
            if override:
                os.environ.update(values)
            else:
                for key, val in values.items():
                    os.environ.setdefault(key, val)
            return values
    return {}
