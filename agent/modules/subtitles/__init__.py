"""Subtitle layer: window a transcript, burn it into a video (separate artifact)."""

from .subs import (
    SubtitleError,
    build_style,
    burn,
    dedupe,
    find_numbers,
    load,
    parse,
    to_srt,
    window,
    write_srt,
)

__all__ = [
    "SubtitleError", "parse", "load", "dedupe", "window",
    "to_srt", "write_srt", "build_style", "burn", "find_numbers",
]
