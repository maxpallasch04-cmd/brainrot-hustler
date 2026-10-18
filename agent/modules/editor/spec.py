"""Spec laden und Felder parsen.

Ein Rezept ist ein JSON-Objekt; die Aufteilung (wie viele Regionen, welche
Größe, welche Position) ist pro Rezept frei. Hier wird nur die *Struktur*
gelesen — inhaltliche Erwartungen stehen im Rezept selbst (`expect`).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_SIZE = (1080, 1920)
DEFAULT_FPS = 30
FITS = ("cover", "contain", "stretch")

_HEX = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_COLOR_NAME = re.compile(r"^[a-zA-Z]+$")


class SpecError(ValueError):
    """Rezept ungültig (Struktur, Pfad oder Render-Parameter)."""


@dataclass
class Spec:
    """Rezept + Herkunft (relative Pfade werden gegen den Rezeptordner gelöst)."""

    data: dict
    path: Path | None = None
    _probes: dict = field(default_factory=dict, repr=False)

    @property
    def base_dir(self) -> Path:
        return self.path.parent if self.path else Path.cwd()

    @property
    def size(self) -> tuple[int, int]:
        return parse_size(self.data.get("size", DEFAULT_SIZE))

    @property
    def fps(self) -> int:
        return parse_fps(self.data.get("fps", DEFAULT_FPS))

    def resolve(self, value) -> Path:
        p = Path(str(value))
        return p if p.is_absolute() else (self.base_dir / p)


def coerce(obj) -> Spec:
    """Spec | Pfad | dict -> Spec."""
    if isinstance(obj, Spec):
        return obj
    if isinstance(obj, (str, Path)):
        return load(obj)
    if isinstance(obj, dict):
        return Spec(dict(obj))
    raise SpecError(f"spec must be a dict, path or Spec, got {type(obj).__name__}")


def load(path) -> Spec:
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecError(f"cannot read spec {p}: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SpecError(f"spec {p} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SpecError(f"spec {p} must be a JSON object")
    return Spec(data, p.resolve())


# ---- Feldparser ---------------------------------------------------------

def _is_num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_size(value) -> tuple[int, int]:
    if isinstance(value, str):
        parts = re.split(r"\s*[x*,:]\s*", value.strip())
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    else:
        raise SpecError(f"size must be [w,h] or 'WxH', got {value!r}")
    if len(parts) != 2:
        raise SpecError(f"size needs exactly two values, got {value!r}")
    try:
        w, h = int(float(parts[0])), int(float(parts[1]))
    except (TypeError, ValueError) as exc:
        raise SpecError(f"size values must be numbers, got {value!r}") from exc
    if w <= 0 or h <= 0:
        raise SpecError(f"size values must be positive, got {value!r}")
    return w, h


def parse_box(value) -> tuple[int, int, int, int]:
    if isinstance(value, str):
        parts = [p for p in re.split(r"\s*[,:]\s*", value.strip()) if p]
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    else:
        raise SpecError(f"box must be [x,y,w,h], got {value!r}")
    if len(parts) != 4:
        raise SpecError(f"box needs exactly four values, got {value!r}")
    try:
        x, y, w, h = (int(float(p)) for p in parts)
    except (TypeError, ValueError) as exc:
        raise SpecError(f"box values must be numbers, got {value!r}") from exc
    if w <= 0 or h <= 0:
        raise SpecError(f"box width/height must be positive, got {value!r}")
    return x, y, w, h


def parse_position(value) -> tuple[int, int] | str:
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("center", "centre"):
            return "center"
        raise SpecError(f"position must be [x,y] or 'center', got {value!r}")
    if isinstance(value, (list, tuple)):
        if len(value) != 2:
            raise SpecError(f"position needs exactly two values, got {value!r}")
        try:
            return int(float(value[0])), int(float(value[1]))
        except (TypeError, ValueError) as exc:
            raise SpecError(f"position values must be numbers, got {value!r}") from exc
    raise SpecError(f"position must be [x,y] or 'center', got {value!r}")


def parse_fit(value) -> str:
    v = str(value).strip().lower()
    if v not in FITS:
        raise SpecError(f"fit must be one of {FITS}, got {value!r}")
    return v


def parse_fps(value) -> int:
    if not _is_num(value):
        raise SpecError(f"fps must be a number, got {value!r}")
    fps = int(value)
    if fps <= 0 or fps > 240:
        raise SpecError(f"fps out of range, got {value!r}")
    return fps


def parse_color(value) -> str:
    """Farbe -> ffmpeg-Wert (`0xRRGGBB` oder Name)."""
    if isinstance(value, (list, tuple)):
        if len(value) != 3:
            raise SpecError(f"color needs [r,g,b], got {value!r}")
        try:
            r, g, b = (int(c) for c in value)
        except (TypeError, ValueError) as exc:
            raise SpecError(f"color channels must be ints, got {value!r}") from exc
        if not all(0 <= c <= 255 for c in (r, g, b)):
            raise SpecError(f"color channels must be 0..255, got {value!r}")
        return f"0x{r:02X}{g:02X}{b:02X}"

    if not isinstance(value, str):
        raise SpecError(f"color must be a string or [r,g,b], got {value!r}")

    raw = value.strip()
    if raw.lower() in ("none", "transparent"):
        raise SpecError("background cannot be transparent")
    m = _HEX.match(raw)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return "0x" + h.upper()
    if _COLOR_NAME.match(raw):
        return raw.lower()
    raise SpecError(f"unrecognized color {value!r} (use #RRGGBB, [r,g,b] or a name)")


def parse_time(value, *, name: str = "time") -> float:
    if not _is_num(value):
        raise SpecError(f"{name} must be a number of seconds, got {value!r}")
    t = float(value)
    if t < 0:
        raise SpecError(f"{name} must be >= 0, got {value!r}")
    return t


def even(value: int) -> int:
    """h264/yuv420p braucht gerade Kantenlängen."""
    return value - (value % 2)
