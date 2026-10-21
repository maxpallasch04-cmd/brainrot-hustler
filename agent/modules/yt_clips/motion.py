"""Cheap motion measurement for clip anchors.

Why this exists: the start of a clip must be **measured**, not estimated from a
transcript or a score anchor. A frame-difference profile over a source window
finds the first/last actually moving frame for a few milliseconds of CPU — no
vision model, no API, no extra dependencies.

The profile is intentionally coarse: ffmpeg decodes at ``fps`` (default 4),
converts to grayscale and scales to ``width`` px before the data reaches Python.
That separates "static scoreboard / replay / standstill" from "skater is moving"
without ever holding a full frame in memory.
"""

from __future__ import annotations

import numpy as np

from . import media

DEFAULT_FPS = 4.0
DEFAULT_WIDTH = 160
DEFAULT_FLOOR = 0.005      # 0.5 % mean pixel change ~= 1.3 grey levels
DEFAULT_MERGE_GAP = 0.4    # join motion runs separated by < 0.4 s


def profile(path, *, start: float = 0.0, end: float | None = None,
            fps: float = DEFAULT_FPS, width: int = DEFAULT_WIDTH,
            threshold: float | None = None,
            merge_gap: float = DEFAULT_MERGE_GAP) -> dict:
    """Measure movement in ``[start, end)`` and return the motion spans.

    Returns ``first_motion`` / ``last_motion`` (seconds, ``None`` when nothing
    moves), the contiguous motion ``segments``, and the sampling parameters so a
    caller can judge whether the measurement is sensitive enough.
    """
    info = media.video_info(path)
    duration = float(info.get("duration") or 0.0)
    end = duration if end is None else min(float(end), duration)
    start = max(0.0, float(start))
    if end <= start or end - start < 0.2:
        raise ValueError(f"window too short: {start:.2f}..{end:.2f}s")
    step = 1.0 / max(0.5, float(fps))

    diffs: list[float] = []
    prev = None
    for _, frame in media.iter_gray_frames(path, start=start, end=end,
                                           fps=fps, width=width):
        small = frame.astype(np.float32)
        if prev is None or prev.shape != small.shape:
            diffs.append(0.0)
        else:
            diffs.append(float(np.abs(small - prev).mean()) / 255.0)
        prev = small
    if not diffs:
        raise ValueError("empty window")
    times = [start + i * step for i in range(len(diffs))]

    arr = np.asarray(diffs, dtype=np.float32)
    if threshold is None:
        # Fixed floor, not median-based: in a sports clip most frames move, so
        # "median * 3" would sit above the signal and report no motion at all.
        threshold = DEFAULT_FLOOR
    moving = arr > float(threshold)

    raw: list[list[float]] = []
    run_start: int | None = None
    for i, is_moving in enumerate(moving):
        if is_moving and run_start is None:
            run_start = i
        elif not is_moving and run_start is not None:
            raw.append([float(times[run_start]), float(times[i - 1]) + step])
            run_start = None
    if run_start is not None:
        raw.append([float(times[run_start]), float(times[-1]) + step])

    merged: list[list[float]] = []
    for seg_start, seg_end in raw:
        if merged and seg_start - merged[-1][1] <= float(merge_gap):
            merged[-1][1] = seg_end
        else:
            merged.append([seg_start, seg_end])

    return {
        "from": round(start, 3),
        "to": round(end, 3),
        "fps": float(fps),
        "width": int(width),
        "threshold": round(float(threshold), 6),
        "first_motion": round(merged[0][0], 3) if merged else None,
        "last_motion": round(merged[-1][1], 3) if merged else None,
        "moving_ratio": round(float(moving.mean()) if moving.size else 0.0, 3),
        "segments": [{"start": round(s, 3), "end": round(e, 3)}
                     for s, e in merged],
    }
