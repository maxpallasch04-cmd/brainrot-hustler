"""Editor — JSON-Spec → ffmpeg.

Nur ffmpeg + stdlib, kein MoviePy.
"""

from .spec import (
    DEFAULT_FPS,
    DEFAULT_SIZE,
    FITS,
    Spec,
    SpecError,
    coerce,  # pyright: ignore[reportUnknownVariableType]
    load, # pyright: ignore[reportUnknownVariableType]
    parse_box,# pyright: ignore[reportUnknownVariableType]
    parse_color,# pyright: ignore[reportUnknownVariableType]
    parse_fit,# pyright: ignore[reportUnknownVariableType]
    parse_fps,# pyright: ignore[reportUnknownVariableType]
    parse_position,# pyright: ignore[reportUnknownVariableType]
    parse_size,# pyright: ignore[reportUnknownVariableType]
)
from .probe import ProbeError, probe # pyright: ignore[reportUnknownVariableType]
from .frames import frames# pyright: ignore[reportUnknownVariableType]
from .validate import validate# pyright: ignore[reportUnknownVariableType]
from .render import render# pyright: ignore[reportUnknownVariableType]

__all__ = [
    "DEFAULT_FPS",
    "DEFAULT_SIZE",
    "FITS",
    "ProbeError",
    "Spec",
    "SpecError",
    "coerce",
    "frames",
    "load",
    "parse_box",
    "parse_color",
    "parse_fit",
    "parse_fps",
    "parse_position",
    "parse_size",
    "probe",
    "render",
    "validate",
]
