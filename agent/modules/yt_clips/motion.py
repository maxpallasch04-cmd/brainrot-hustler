"""Cheap motion measurement for clip anchors.

Why this exists: the start of a clip must be **measured**, not estimated from a
transcript or a score anchor. A frame-difference profile over a source window
finds the first/last actually moving frame for a few milliseconds of CPU — no
vision model, no API, no extra dependencies.

The profile is intentionally coarse: frames are decoded at ``fps`` (default 4),
converted to grayscale and downscaled to ``width`` px before diffing. That is
enough to separate "static scoreboard / replay / standstill" from "skater is
moving" without holding full frames in memory.
"""

from __future__ import annotations

import numpy as np

DEFAULT_FPS = 4.0
DEFAULT_WIDTH = 160
DEFAULT_FLOOR = 0.005      # 0.5 % mean pixel change ~= 1.3 grey levels
DEFAULT_MERGE_GAP = 0.4    # join motion runs separated by < 0.4 s


def _small_gray(frame, width: int) -> np.ndarray:
    gray = frame.mean(axis=2) if frame.ndim == 3 else frame
    h, w = gray.shape[:2]
    stride = max(1, int(round(w / float(max(1, width)))))
    return gray[::stride, ::stride].astype(np.float32)


def profile(path, *, start: float = 0.0, end: float | None = None,
            fps: float = DEFAULT_FPS, width: int = DEFAULT_WIDTH,
            threshold: float | None = None,
            merge_gap: float = DEFAULT_MERGE_GAP) -> dict:
    """Measure movement in ``[start, end)`` and return the motion spans.

    Returns ``first_motion`` / ``last_motion`` (seconds, ``None`` when nothing
    moves), the contiguous motion ``segments``, and the sampling parameters so a
    caller can judge whether the measurement is sensitive enough.
    """
    from moviepy import VideoFileClip

    clip = VideoFileClip(str(path))
    try:
        duration = float(clip.duration or 0.0)
        end = duration if end is None else min(float(end), duration)
        start = max(0.0, float(start))
        if end <= start or end - start < 0.2:
            raise ValueError(f"window too short: {start:.2f}..{end:.2f}s")
        step = 1.0 / max(0.5, float(fps))
        times = list(np.arange(start, end, step))
        if not times:
            raise ValueError("empty window")

        diffs: list[float] = []
        prev = None
        for t in times:
            frame = clip.get_frame(min(max(t, 0.0), max(0.0, duration - 1e-3)))
            small = _small_gray(frame, width)
            if prev is None or prev.shape != small.shape:
                diffs.append(0.0)
            else:
                diffs.append(float(np.abs(small - prev).mean()) / 255.0)
            prev = small
    finally:
        clip.close()

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
        "segments": [{"start": round(s, 3), "end": round(e, 3)} for s, e in merged],
    }
