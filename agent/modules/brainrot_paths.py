"""Workspace-Pfade und Kanal-Auswahl.

Alles, was der Agent produziert, liegt unter ``memory/``; Code liegt in ``modules/``.
Der aktive Kanal kommt aus ``BRAINROT_CHANNEL`` (setzt ``bin/cli --channel``).

Layout::

    memory/
      brainrot.db            eine DB, alle Kanäle (Spalte channel_id)
      <channel>/videos/      fertige Renders
      <channel>/clips/       Rohmaterial
      <channel>/screenshots/ Frames, Crops
      <channel>/specs/       Editor-Specs
"""

from __future__ import annotations

import os
import re
from pathlib import Path

CHANNEL_ENV = "BRAINROT_CHANNEL"

# <workspace>/modules/brainrot_paths.py -> <workspace>
WORKSPACE = Path(__file__).resolve().parent.parent
MEMORY = WORKSPACE / "memory"
DB = MEMORY / "brainrot.db"

CHANNEL_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")

KINDS = ("videos", "clips", "screenshots", "specs")


class ChannelError(RuntimeError):
    """Kein (gültiger) Kanal gesetzt oder Kanal unbekannt."""


def valid_channel(value: str) -> str:
    value = (value or "").strip().lower()
    if not CHANNEL_PATTERN.match(value):
        raise ChannelError(
            f"ungültige Kanal-ID {value!r}: erlaubt sind a-z, 0-9, '-' und '_' "
            f"(max. 32 Zeichen), z. B. 'sls'"
        )
    return value


def channel(required: bool = False) -> str | None:
    """Aktiver Kanal aus der Umgebung (``None``, wenn nicht gesetzt)."""
    value = (os.environ.get(CHANNEL_ENV) or "").strip()
    if not value:
        if required:
            raise ChannelError(
                "kein Kanal gesetzt - Aufruf über 'bin/channel <id> <modul>.cli ...' "
                f"(setzt {CHANNEL_ENV})"
            )
        return None
    return valid_channel(value)


def memory_root() -> Path:
    return MEMORY


def db_path() -> Path:
    return DB


def channel_dir(kind: str, channel_id: str | None = None) -> Path:
    """``memory/<channel>/<kind>`` - ohne Kanal gemeinsam ``memory/<kind>``."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    ch = channel_id or channel()
    root = memory_root() / ch if ch else memory_root()
    return root / kind
