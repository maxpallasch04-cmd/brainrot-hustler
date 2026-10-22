"""YouTube-URLs: nur die Video-ID, nichts wird geladen.

Der Download läuft nicht mehr hier: der Operator lädt und hostet, `fetch`
holt die Datei aus dem Bucket. Dieses Modul ist der einzige Ort, der noch
YouTube-URLs anfasst — für `request` (Quelle anlegen, Dateiname ableiten).
"""

from __future__ import annotations

import re

_YT_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/|/v/)([A-Za-z0-9_-]{6,})")


def youtube_id(url: str) -> str | None:
    """Best-effort YouTube video id from a URL (watch / youtu.be / shorts)."""
    m = _YT_ID.search(str(url))
    return m.group(1) if m else None
